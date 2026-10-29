"""Settings, i18n, PDT OAuth/MCP sync, and Vault Backup APIRouter."""

from __future__ import annotations

import contextlib
import copy
import ipaddress
import json
import secrets
import tempfile
import time
import urllib.parse
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from paslood import __version__
from paslood.adapters.ingestion.pdt_auth import PdtAuthManager, generate_pkce_pair
from paslood.adapters.ingestion.pdt_mcp import PdtMcpGateway
from paslood.adapters.repositories.config_repo import (
    ConfigRepository,
    _is_masked_secret,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.adapters.security.secret_vault import SecretVault
from paslood.adapters.settings import AppSettings
from paslood.delivery.web.auth import AuthManager
from paslood.delivery.web.dependencies import (
    get_app_settings,
    get_auth_manager,
    get_db,
    get_repo,
    get_secret_vault,
)
from paslood.delivery.web.helpers import _PinnedMcpNetworkBackend
from paslood.delivery.web.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    get_translations_for_locale,
)
from paslood.domain.account import KnownAccount

router = APIRouter(tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    ai: dict[str, Any] | None = None
    tax: dict[str, Any] | None = None
    pdt: dict[str, Any] | None = None
    language: str | None = None
    regional_format: str | None = None
    onboarding_complete: bool | None = None


class PdtManualTokenRequest(BaseModel):
    auth_token: str
    mcp_url: str | None = None


class CustomMcpServerRequest(BaseModel):
    name: str
    url: str
    transport: str = "http"
    auth_token: str | None = None
    enabled: bool = True


class McpTestRequest(BaseModel):
    url: str
    auth_token: str | None = None


class BackupExportRequest(BaseModel):
    passphrase: str


class BackupImportRequest(BaseModel):
    bundle: dict[str, Any]
    passphrase: str


class CloudSyncRequest(BaseModel):
    sync_dir: str
    passphrase: str
    action: str = "push"  # "push" or "pull"


async def _get_valid_pdt_token(
    repo: ConfigRepository,
    secret_vault: SecretVault,
    pdt_cfg: dict[str, Any],
    force_refresh: bool = False,
) -> str | None:
    token = pdt_cfg.get("auth_token")
    refresh_tok = pdt_cfg.get("refresh_token")
    client_id = pdt_cfg.get("client_id") or "paslood-client"
    expires_at = pdt_cfg.get("expires_at")

    should_refresh = force_refresh or (
        expires_at is not None and float(expires_at) < (time.time() + 60)
    )
    if should_refresh and refresh_tok:
        try:
            new_tokens = await PdtAuthManager.refresh_tokens(
                client_id=client_id, refresh_token=refresh_tok
            )
            if not new_tokens.get("refresh_token"):
                new_tokens["refresh_token"] = refresh_tok
            repo.save_pdt_tokens(new_tokens)
            return str(new_tokens.get("access_token") or token)
        except Exception:
            pass
    if token and token.startswith("enc:"):
        token = secret_vault.decrypt(token)
    return token


@router.get("/api/settings")
async def get_settings(
    repo: ConfigRepository = Depends(get_repo),
    secret_vault: SecretVault = Depends(get_secret_vault),
):
    raw_settings = repo.load_settings()
    masked = copy.deepcopy(raw_settings)
    if masked.get("ai", {}).get("api_key"):
        raw_k = masked["ai"]["api_key"]
        decrypted_k = secret_vault.decrypt(raw_k)
        k = decrypted_k if decrypted_k else raw_k
        masked["ai"]["api_key"] = ("••••" + k[-4:]) if len(k) > 4 else "••••••••"
    if masked.get("pdt", {}).get("auth_token"):
        raw_t = masked["pdt"]["auth_token"]
        decrypted_t = secret_vault.decrypt(raw_t)
        t = decrypted_t if decrypted_t else raw_t
        masked["pdt"]["auth_token"] = ("••••" + t[-4:]) if len(t) > 4 else "••••••••"
    return masked


@router.post("/api/settings")
async def update_settings(
    req: SettingsUpdateRequest,
    repo: ConfigRepository = Depends(get_repo),
    secret_vault: SecretVault = Depends(get_secret_vault),
):
    data = req.model_dump(exclude_unset=True)
    if data.get("ai", {}).get("api_key") and not _is_masked_secret(data["ai"]["api_key"]):
        data["ai"]["api_key"] = secret_vault.encrypt(data["ai"]["api_key"])
    if data.get("pdt", {}).get("auth_token") and not _is_masked_secret(data["pdt"]["auth_token"]):
        data["pdt"]["auth_token"] = secret_vault.encrypt(data["pdt"]["auth_token"])
    repo.save_settings(data)
    return {"status": "success"}


@router.get("/api/i18n")
async def get_i18n_bundle():
    return {
        "supported_languages": SUPPORTED_LANGUAGES,
        "default_language": DEFAULT_LANGUAGE,
        "translations": TRANSLATIONS,
    }


@router.get("/api/i18n/{lang}")
async def get_i18n_lang(lang: str):
    normalized = lang.lower()[:2]
    if normalized not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=404, detail=f"Language '{lang}' is not supported.")
    return {
        "language": normalized,
        "translations": get_translations_for_locale(normalized),
    }


@router.get("/api/auth/pdt/connect")
async def initiate_pdt_oauth(
    request: Request,
    repo: ConfigRepository = Depends(get_repo),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    redirect_uri = request.query_params.get("redirect_uri")
    base_url = str(request.base_url).rstrip("/")
    default_redirect = f"{base_url}/api/auth/pdt/callback"

    if redirect_uri:
        parsed = urllib.parse.urlparse(redirect_uri)
        allowed_hosts = {"localhost", "127.0.0.1", "test", "testserver"}
        if request.url.hostname:
            allowed_hosts.add(request.url.hostname.lower())
        if (parsed.hostname or "").lower() not in allowed_hosts:
            raise HTTPException(
                status_code=400,
                detail="Invalid redirect_uri: only local origins matching the active dashboard are allowed.",
            )
    else:
        redirect_uri = default_redirect

    parsed = urllib.parse.urlparse(redirect_uri)
    variants = [redirect_uri]
    if "127.0.0.1" in parsed.netloc:
        variants.append(redirect_uri.replace("127.0.0.1", "localhost"))
    elif "localhost" in parsed.netloc:
        variants.append(redirect_uri.replace("localhost", "127.0.0.1"))

    try:
        client_id = await PdtAuthManager.register_client(
            redirect_uri=redirect_uri, additional_uris=variants
        )
        pdt_cfg = repo.load_settings().get("pdt", {})
        pdt_cfg["client_id"] = client_id
        repo.save_settings({"pdt": pdt_cfg})
    except Exception:
        pdt_cfg = repo.load_settings().get("pdt", {})
        client_id = pdt_cfg.get("client_id") or "paslood-client"

    verifier, challenge = generate_pkce_pair()
    state_token = secrets.token_urlsafe(16)
    auth_manager.save_oauth_state(
        state_token,
        {
            "verifier": verifier,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        },
    )
    auth_url = PdtAuthManager.build_authorization_url(
        client_id, redirect_uri, state_token, challenge
    )
    return {"auth_url": auth_url, "state": state_token}


@router.get("/api/auth/pdt/callback")
async def pdt_oauth_callback(
    request: Request,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    code = request.query_params.get("code")
    state_param = request.query_params.get("state")
    oauth_session = auth_manager.pop_oauth_state(state_param or "")
    if not oauth_session or not code:
        return RedirectResponse(url="/#settings?pdt_error=invalid_or_expired_state")

    try:
        tokens = await PdtAuthManager.exchange_code(
            client_id=oauth_session["client_id"],
            code=code,
            verifier=oauth_session["verifier"],
            redirect_uri=oauth_session["redirect_uri"],
        )
        repo.save_pdt_tokens(tokens)

        synced_count = 0
        try:
            pdt_cfg = repo.load_settings().get("pdt", {})
            gateway = PdtMcpGateway(
                mcp_url=pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com"),
                auth_token=tokens.get("access_token"),
            )
            assets = await gateway.fetch_portfolio_assets()
            if assets:
                db.delete_discovered_assets_by_source("pdt_mcp")
                db.save_discovered_assets(assets, source="pdt_mcp")
            repo.update_pdt_sync_timestamp()
            synced_count = len(assets)
        except Exception:
            pass

        return RedirectResponse(url=f"/#dashboard?pdt_connected=true&synced_count={synced_count}")
    except Exception as e:
        safe_err = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"/#settings?pdt_error={safe_err}")


@router.post("/api/auth/pdt/manual")
async def save_pdt_manual_token(
    req: PdtManualTokenRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    repo.save_pdt_tokens({"access_token": req.auth_token, "client_id": "manual"})
    if req.mcp_url:
        s = repo.load_settings()
        p = s.get("pdt", {})
        p["mcp_url"] = req.mcp_url
        repo.save_settings({"pdt": p})
    return {"status": "success"}


@router.post("/api/auth/pdt/disconnect")
async def disconnect_pdt(
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    repo.disconnect_pdt()
    db.delete_discovered_assets_by_source("pdt_mcp")
    return {"status": "disconnected"}


@router.post("/api/mcp/pdt/sync")
async def sync_pdt_holdings(
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    secret_vault: SecretVault = Depends(get_secret_vault),
):
    s = repo.load_settings()
    pdt_cfg = s.get("pdt", {})
    token = await _get_valid_pdt_token(repo, secret_vault, pdt_cfg)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="PDT is not connected. Please connect via OAuth or provide an API token in Settings.",
        )
    mcp_url = pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com")
    gateway = PdtMcpGateway(mcp_url=mcp_url, auth_token=token)
    try:
        assets = await gateway.fetch_portfolio_assets(raise_on_auth_error=True)
    except httpx.HTTPStatusError:
        refreshed = await _get_valid_pdt_token(repo, secret_vault, pdt_cfg, force_refresh=True)
        if refreshed and refreshed != token:
            gateway = PdtMcpGateway(mcp_url=mcp_url, auth_token=refreshed)
            assets = await gateway.fetch_portfolio_assets()
        else:
            assets = []

    if assets:
        db.delete_discovered_assets_by_source("pdt_mcp")
        db.save_discovered_assets(assets, source="pdt_mcp")
        repo.update_pdt_sync_timestamp()
    else:
        cached_pdt = [a for a in db.get_discovered_assets() if a.id.startswith("pdt-")]
        if cached_pdt:
            assets = cached_pdt

    total_val = sum((a.current_value.amount for a in assets), Decimal("0.00"))
    return {
        "status": "success",
        "asset_count": len(assets),
        "total_value": float(total_val),
        "last_sync": repo.load_settings()["pdt"].get("last_sync"),
    }


@router.post("/api/settings/mcp/servers")
async def add_custom_mcp_server(
    req: CustomMcpServerRequest,
    repo: ConfigRepository = Depends(get_repo),
):
    server_id = f"mcp-{uuid.uuid4().hex[:8]}"
    server_dict = {
        "id": server_id,
        "name": req.name,
        "url": req.url,
        "transport": req.transport,
        "auth_token": req.auth_token,
        "enabled": req.enabled,
    }
    repo.add_mcp_server(server_dict)
    return {"status": "success", "server": server_dict}


@router.delete("/api/settings/mcp/servers/{server_id}")
async def delete_custom_mcp_server(
    server_id: str,
    repo: ConfigRepository = Depends(get_repo),
):
    repo.delete_mcp_server(server_id)
    return {"status": "success"}


@router.post("/api/settings/mcp/servers/test")
async def test_mcp_server(
    req: McpTestRequest,
    settings: AppSettings = Depends(get_app_settings),
):
    parsed = urllib.parse.urlparse(req.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme: only HTTP and HTTPS are permitted.",
        )
    if parsed.username or parsed.password or not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="MCP URL must include a hostname and cannot contain credentials.",
        )
    try:
        hostname = (parsed.hostname or "").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise HTTPException(status_code=400, detail="MCP hostname is invalid.") from exc
    if hostname in ("169.254.169.254", "metadata.google.internal", "metadata.turing"):
        raise HTTPException(
            status_code=403,
            detail="Access to cloud metadata endpoints is prohibited.",
        )
    with contextlib.suppress(ValueError):
        ip = ipaddress.ip_address(hostname)
        if ip.is_link_local:
            raise HTTPException(
                status_code=403,
                detail="Access to link-local metadata addresses is prohibited.",
            )

    pinned_backend = None
    if settings.mode != "local":
        import socket

        try:
            addr_info = socket.getaddrinfo(
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="MCP hostname could not be resolved."
            ) from exc

        resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for info in addr_info:
            try:
                resolved_ips.append(ipaddress.ip_address(info[4][0].split("%", 1)[0]))
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail="MCP hostname resolved to an invalid address."
                ) from exc
        if not resolved_ips:
            raise HTTPException(
                status_code=400, detail="MCP hostname did not resolve to an address."
            )
        for rip in resolved_ips:
            if not rip.is_global:
                raise HTTPException(
                    status_code=403,
                    detail="Access to internal or private network endpoints is prohibited.",
                )
        pinned_backend = _PinnedMcpNetworkBackend(
            hostname, list(dict.fromkeys(str(resolved_ip) for resolved_ip in resolved_ips))
        )

    start_t = time.time()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": f"Paslood/{__version__}",
    }
    if req.auth_token:
        headers["Authorization"] = f"Bearer {req.auth_token}"

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "paslood", "version": __version__},
        },
    }

    try:
        transport = (
            httpx.AsyncHTTPTransport(network_backend=pinned_backend) if pinned_backend else None
        )
        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            resp = await client.post(req.url, json=payload, headers=headers)
            latency_ms = int((time.time() - start_t) * 1000)
            return {
                "status": "success",
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/api/backup/info")
async def get_backup_storage_info(
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    s = repo.load_settings()
    cloud_cfg = s.get("cloud_sync", {})
    return {
        "config_dir": str(repo.config_path.parent),
        "portfolio_yaml": str(repo.config_path),
        "sqlite_db": str(db.db_path),
        "rules_yaml": str(repo.rules_path),
        "cloud_sync_dir": cloud_cfg.get("sync_dir", ""),
        "last_backup": cloud_cfg.get("last_backup"),
    }


@router.post("/api/backup/export")
async def export_encrypted_backup(
    req: BackupExportRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    try:
        payload = {
            "config": repo.export_raw_config(),
            "database": db.export_state_dict(),
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        bundle = encrypt_vault_payload(payload, req.passphrase)
        return bundle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/backup/import")
async def import_encrypted_backup(
    req: BackupImportRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    try:
        decrypted = decrypt_vault_payload(req.bundle, req.passphrase)
        if "config" in decrypted:
            repo.import_raw_config(decrypted["config"])
        if "database" in decrypted:
            db.import_state_dict(decrypted["database"])
        return {"status": "success", "exported_at": decrypted.get("exported_at")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _is_safe_cloud_sync_path(target_path: Path | str, data_dir: Path | None = None) -> bool:
    raw = str(target_path).strip()
    if not raw or raw == "/" or raw == "~":
        return False

    # Disallow relative paths that do not start with ~ or / (prevent resolving relative to CWD)
    if not (raw.startswith("~") or Path(raw).is_absolute()):
        return False

    try:
        resolved = Path(raw).expanduser().resolve()
    except Exception:
        return False

    if resolved == Path("/") or resolved == Path(resolved.anchor):
        return False

    temp_dir = Path(tempfile.gettempdir()).resolve()
    home_dir = Path.home().resolve()

    # Reject bare root of user home or tempdir
    if resolved in (home_dir, temp_dir):
        return False

    allowed_roots = [home_dir, temp_dir]
    if data_dir:
        allowed_roots.append(Path(data_dir).resolve())

    inside_allowed = any(root in resolved.parents for root in allowed_roots)
    if not inside_allowed:
        return False

    forbidden_prefixes = [
        Path("/etc"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/System"),
        Path("/dev"),
        Path("/proc"),
        Path("/sys"),
        Path("C:\\Windows"),
        Path("C:\\Program Files"),
        Path("C:\\Program Files (x86)"),
    ]
    for forbidden in forbidden_prefixes:
        try:
            if resolved == forbidden or forbidden in resolved.parents:
                return False
        except Exception:
            pass

    return True


@router.post("/api/backup/cloud-sync")
async def sync_encrypted_vault_with_cloud_folder(
    req: CloudSyncRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
    settings: AppSettings = Depends(get_app_settings),
):
    if settings.mode != "local":
        raise HTTPException(
            status_code=403,
            detail="Cloud folder sync with server filesystem paths is disabled in remote/container mode. Please use encrypted export/import in Settings.",
        )
    raw_dir = req.sync_dir.strip()
    if not _is_safe_cloud_sync_path(raw_dir, getattr(settings, "data_dir", None)):
        raise HTTPException(
            status_code=400,
            detail="Invalid cloud sync directory: path must be within user home or application data directory.",
        )
    sync_path = Path(raw_dir).expanduser().resolve()
    vault_file = sync_path / "paslood_vault.wpbackup"

    try:
        if req.action == "pull":
            if not vault_file.exists():
                raise HTTPException(
                    status_code=404,
                    detail=f"No vault file found at {vault_file}",
                )
            with open(vault_file, encoding="utf-8") as f:
                bundle = json.load(f)
            decrypted = decrypt_vault_payload(bundle, req.passphrase)
            if "config" in decrypted:
                repo.import_raw_config(decrypted["config"])
            if "database" in decrypted:
                db.import_state_dict(decrypted["database"])
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            repo.save_settings({"cloud_sync": {"sync_dir": str(sync_path), "last_backup": now_str}})
            return {
                "status": "success",
                "action": "pull",
                "vault_file": str(vault_file),
                "last_backup": now_str,
            }
        else:
            sync_path.mkdir(parents=True, exist_ok=True)
            payload = {
                "config": repo.export_raw_config(),
                "database": db.export_state_dict(),
                "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            bundle = encrypt_vault_payload(payload, req.passphrase)
            with open(vault_file, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2)
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            repo.save_settings({"cloud_sync": {"sync_dir": str(sync_path), "last_backup": now_str}})
            return {
                "status": "success",
                "action": "push",
                "vault_file": str(vault_file),
                "last_backup": now_str,
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class KnownAccountRequest(BaseModel):
    id: str | None = None
    account_number: str
    label: str
    account_type: str = "CHECKING"
    institution: str = ""


@router.get("/api/accounts/known")
async def list_known_accounts(repo: ConfigRepository = Depends(get_repo)):
    accounts = repo.load_known_accounts()
    return {
        "accounts": [
            {
                "id": a.id,
                "account_number": a.account_number,
                "label": a.label,
                "account_type": a.account_type,
                "institution": a.institution,
            }
            for a in accounts
        ]
    }


@router.post("/api/accounts/known")
async def create_or_update_known_account(
    req: KnownAccountRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    acc_id = req.id or f"acc-{uuid.uuid4().hex[:8]}"
    account = KnownAccount(
        id=acc_id,
        account_number=req.account_number.strip(),
        label=req.label.strip(),
        account_type=req.account_type.upper().strip(),
        institution=req.institution.strip(),
    )
    repo.save_known_account(account)
    updated_txs = db.apply_known_account_to_transactions(
        account_number=account.account_number,
        label=account.label,
        account_type=account.account_type,
    )
    return {
        "status": "success",
        "updated_transactions_count": updated_txs,
        "account": {
            "id": account.id,
            "account_number": account.account_number,
            "label": account.label,
            "account_type": account.account_type,
            "institution": account.institution,
        },
    }


@router.put("/api/accounts/known/{account_id}")
async def update_known_account_endpoint(
    account_id: str,
    req: KnownAccountRequest,
    repo: ConfigRepository = Depends(get_repo),
    db: LocalDbRepository = Depends(get_db),
):
    account = KnownAccount(
        id=account_id,
        account_number=req.account_number.strip(),
        label=req.label.strip(),
        account_type=req.account_type.upper().strip(),
        institution=req.institution.strip(),
    )
    repo.save_known_account(account)
    updated_txs = db.apply_known_account_to_transactions(
        account_number=account.account_number,
        label=account.label,
        account_type=account.account_type,
    )
    return {
        "status": "success",
        "updated_transactions_count": updated_txs,
        "account": {
            "id": account.id,
            "account_number": account.account_number,
            "label": account.label,
            "account_type": account.account_type,
            "institution": account.institution,
        },
    }


@router.delete("/api/accounts/known/{account_id}")
async def delete_known_account_endpoint(
    account_id: str,
    repo: ConfigRepository = Depends(get_repo),
):
    repo.delete_known_account(account_id)
    return {"status": "success"}


@router.get("/api/accounts/discovered")
async def list_discovered_accounts(
    db: LocalDbRepository = Depends(get_db),
    repo: ConfigRepository = Depends(get_repo),
):
    discovered = db.get_discovered_account_summaries()
    known = repo.load_known_accounts()
    clean_known = {
        "".join(ch for ch in k.account_number.upper() if ch.isalnum()): k
        for k in known
        if k.account_number
    }

    results = []
    for d in discovered:
        clean_acc = "".join(ch for ch in d["account_id"].upper() if ch.isalnum())
        match = clean_known.get(clean_acc)
        results.append(
            {
                "account_id": d["account_id"],
                "institution_hint": d["institution_hint"],
                "transaction_count": d["transaction_count"],
                "has_cash_asset": d["has_cash_asset"],
                "is_known": match is not None,
                "known_id": match.id if match else None,
                "known_label": match.label if match else None,
                "known_type": match.account_type if match else None,
            }
        )

    return {"discovered_accounts": results}
