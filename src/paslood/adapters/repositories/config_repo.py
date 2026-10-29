"""Config Repository for managing Buckets, Manual Accounts, and Classification Rules."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from paslood.domain.account import KnownAccount
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.bucket import AllocationRule, Bucket
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money

if TYPE_CHECKING:
    from paslood.adapters.security.secret_vault import SecretVault


def _decimal_representer(dumper: Any, data: Decimal) -> Any:
    return dumper.represent_scalar("tag:yaml.org,2002:float", str(data))


yaml.add_representer(Decimal, _decimal_representer)
yaml.add_representer(Decimal, _decimal_representer, Dumper=yaml.SafeDumper)


def _is_masked_secret(val: Any) -> bool:
    """Checks whether a secret string is a UI masked placeholder (e.g. '••••1234')."""
    if not isinstance(val, str):
        return False
    stripped = val.strip()
    return "•" in stripped or stripped.startswith("****")


def encrypt_vault_payload(payload_dict: dict[str, Any], passphrase: str) -> dict[str, Any]:
    """Encrypts a dictionary payload using PBKDF2-HMAC-SHA256 + standard AES-256-GCM authenticated encryption."""
    if not passphrase or len(passphrase.strip()) < 4:
        raise ValueError("Passphrase must be at least 4 characters long.")

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)  # Standard 96-bit AES-GCM nonce
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)

    plaintext = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "format": "paslood-encrypted-vault-v2",
        "encrypted": True,
        "kdf": "PBKDF2-HMAC-SHA256-200000",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decrypt_vault_payload(bundle: dict[str, Any], passphrase: str) -> dict[str, Any]:
    """Decrypts a vault bundle with AES-256-GCM v2, with fallback for legacy v1 CTR-XOR bundles."""
    if not bundle.get("encrypted"):
        raise ValueError("Invalid vault bundle: not marked as encrypted.")

    try:
        salt = base64.b64decode(bundle["salt"])
        nonce = base64.b64decode(bundle["nonce"])
        ciphertext = base64.b64decode(bundle["ciphertext"])
    except Exception as e:
        raise ValueError("Malformed vault bundle fields.") from e

    fmt = bundle.get("format", "paslood-encrypted-vault-v1")
    if fmt == "paslood-encrypted-vault-v2":
        key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
        try:
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            raise ValueError(
                "Decryption failed: invalid passphrase or tampered backup file."
            ) from e

    # Legacy v1 CTR-XOR backward compatibility
    expected_mac = str(bundle.get("mac", ""))
    derived = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=64)
    enc_key = derived[:32]
    mac_key = derived[32:]

    actual_mac = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(actual_mac, expected_mac):
        raise ValueError("Decryption failed: invalid passphrase or tampered backup file.")

    keystream = bytearray()
    block_count = (len(ciphertext) + 31) // 32
    for counter in range(block_count):
        counter_bytes = nonce + counter.to_bytes(8, "big")
        keystream.extend(hmac.new(enc_key, counter_bytes, hashlib.sha256).digest())

    plaintext = bytes(c ^ k for c, k in zip(ciphertext, keystream[: len(ciphertext)], strict=False))
    return json.loads(plaintext.decode("utf-8"))


def _secure_file_perms(path: Path) -> None:
    """Set restrictive 0o600 permissions on sensitive configuration and token files."""
    if os.name != "nt" and path.exists():
        with contextlib.suppress(Exception):
            os.chmod(path, 0o600)


def _secure_dir_perms(path: Path) -> None:
    """Set restrictive 0o700 permissions on configuration directory."""
    if os.name != "nt" and path.exists():
        with contextlib.suppress(Exception):
            os.chmod(path, 0o700)


DEFAULT_BUCKETS_CONFIG: list[dict[str, Any]] = [
    {
        "id": "core-etf",
        "name": "Core World ETFs",
        "target_weight_pct": 50.0,
        "drift_tolerance_pct": 3.0,
        "color": "#3B82F6",
        "rules": [
            {"asset_classes": ["ETF"]},
            {"symbols": ["VWCE", "IWDA", "EMIM"]},
        ],
    },
    {
        "id": "tech-growth",
        "name": "High-Conviction Tech",
        "target_weight_pct": 35.0,
        "drift_tolerance_pct": 5.0,
        "color": "#10B981",
        "rules": [
            {"symbols": ["NVDA", "AAPL", "MSFT", "GOOGL"]},
        ],
    },
    {
        "id": "commodities",
        "name": "Gold & Commodities",
        "target_weight_pct": 5.0,
        "drift_tolerance_pct": 2.0,
        "color": "#F59E0B",
        "rules": [
            {"asset_classes": ["COMMODITY"]},
            {"name_keywords": ["GOLD", "GOUD", "COMMODITY"]},
        ],
    },
    {
        "id": "cash-buffer",
        "name": "Cash & Emergency Buffer",
        "target_weight_pct": 10.0,
        "drift_tolerance_pct": 2.5,
        "color": "#6366F1",
        "rules": [
            {"asset_classes": ["CASH"]},
            {"institutions": ["KBC", "BUNQ"]},
        ],
    },
]


class ConfigRepository:
    """Manages YAML/JSON configuration files for user buckets, accounts, and learned rules."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        data_dir: str | Path | None = None,
        tenant_id: str = "default",
        secret_vault: SecretVault | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.secret_vault = secret_vault
        if config_path:
            self.config_path = Path(config_path)
        else:
            raw_env_dir = os.getenv("PASLOOD_DATA_DIR")
            base_dir = (
                Path(data_dir).expanduser().resolve()
                if data_dir
                else (
                    Path(raw_env_dir).expanduser().resolve()
                    if raw_env_dir
                    else Path.home() / ".paslood"
                )
            )
            if tenant_id != "default":
                self.config_path = base_dir / "tenants" / tenant_id / "portfolio.yaml"
            else:
                self.config_path = base_dir / "portfolio.yaml"

        self.rules_path = self.config_path.parent / "rules.yaml"
        self._ensure_defaults()

    def _get_secret_vault(self) -> SecretVault:
        if self.secret_vault is not None:
            return self.secret_vault
        from paslood.adapters.security.secret_vault import SecretVault
        from paslood.adapters.settings import AppSettings

        return SecretVault(AppSettings.from_env().secret_key)

    @staticmethod
    def _write_yaml_atomic(path: Path, data: Any) -> None:
        """Atomically writes YAML data via a sibling temp file and sets 0o600 permissions."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f, sort_keys=False, indent=2)
                f.flush()
            _secure_file_perms(tmp_path)
            os.replace(tmp_path, path)
            _secure_file_perms(path)
        except Exception:
            with contextlib.suppress(Exception):
                tmp_path.unlink(missing_ok=True)
            raise

    def _ensure_defaults(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        _secure_dir_perms(self.config_path.parent)

        if not self.config_path.exists():
            default_data = {
                "buckets": DEFAULT_BUCKETS_CONFIG,
                "manual_assets": [],
                "manual_liabilities": [],
            }
            self._write_yaml_atomic(self.config_path, default_data)

        if not self.rules_path.exists():
            self._write_yaml_atomic(self.rules_path, [])

    def load_buckets(self) -> list[Bucket]:
        """Loads configured strategic buckets with allocation rules."""
        if not self.config_path.exists():
            return []

        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_buckets = data.get("buckets", [])
        buckets: list[Bucket] = []

        for b in raw_buckets:
            rules: list[AllocationRule] = []
            for r in b.get("rules", []):
                syms = set(r.get("symbols", []))
                isins = set(r.get("isins", []))
                insts = set(r.get("institutions", []))
                keywords = set(r.get("name_keywords", []))
                classes = {
                    AssetClass(c) for c in r.get("asset_classes", []) if c in AssetClass.__members__
                }
                rules.append(
                    AllocationRule(
                        symbols=syms,
                        isins=isins,
                        asset_classes=classes,
                        institutions=insts,
                        name_keywords=keywords,
                    )
                )

            buckets.append(
                Bucket(
                    id=str(b.get("id")),
                    name=str(b.get("name")),
                    target_weight_pct=Decimal(str(b.get("target_weight_pct", 0.0))),
                    drift_tolerance_pct=Decimal(str(b.get("drift_tolerance_pct", 3.0))),
                    rules=rules,
                    color=str(b.get("color", "#3B82F6")),
                    description=str(b.get("description", "")),
                    include_in_rebalancing=bool(b.get("include_in_rebalancing", True)),
                    include_in_net_worth=bool(b.get("include_in_net_worth", True)),
                )
            )

        return buckets

    def save_bucket_target(self, bucket_id: str, name: str, target_weight_pct: Decimal) -> None:
        """Updates or creates a bucket allocation target in portfolio.yaml."""
        self.save_bucket(
            {"id": bucket_id, "name": name, "target_weight_pct": float(target_weight_pct)}
        )

    def save_bucket_targets(self, targets: dict[str, Decimal | float]) -> None:
        """Batch updates target weight percentages for multiple buckets."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        buckets = data.get("buckets", [])
        for b in buckets:
            bid = b.get("id")
            if bid in targets:
                b["target_weight_pct"] = float(targets[bid])

        data["buckets"] = buckets
        self._write_yaml_atomic(self.config_path, data)

    def save_bucket(self, bucket_data: dict[str, Any]) -> str:
        """Adds or updates a strategic allocation bucket in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        buckets = data.get("buckets", [])
        bucket_id = str(bucket_data.get("id") or f"bucket-{uuid.uuid4().hex[:8]}")
        existing = next((b for b in buckets if b.get("id") == bucket_id), None)
        if existing:
            if "name" in bucket_data:
                existing["name"] = bucket_data["name"]
            if "target_weight_pct" in bucket_data:
                existing["target_weight_pct"] = float(bucket_data["target_weight_pct"])
            if "color" in bucket_data and bucket_data["color"]:
                existing["color"] = bucket_data["color"]
            if (
                "drift_tolerance_pct" in bucket_data
                and bucket_data["drift_tolerance_pct"] is not None
            ):
                existing["drift_tolerance_pct"] = float(bucket_data["drift_tolerance_pct"])
            if "description" in bucket_data:
                existing["description"] = bucket_data["description"]
            if (
                "include_in_rebalancing" in bucket_data
                and bucket_data["include_in_rebalancing"] is not None
            ):
                existing["include_in_rebalancing"] = bool(bucket_data["include_in_rebalancing"])
            if (
                "include_in_net_worth" in bucket_data
                and bucket_data["include_in_net_worth"] is not None
            ):
                existing["include_in_net_worth"] = bool(bucket_data["include_in_net_worth"])
        else:
            palette = [
                "#3B82F6",
                "#10B981",
                "#F59E0B",
                "#8B5CF6",
                "#EC4899",
                "#06B6D4",
                "#F97316",
                "#6366F1",
            ]
            chosen_color = bucket_data.get("color") or palette[len(buckets) % len(palette)]
            include_reb = bool(bucket_data.get("include_in_rebalancing", True))
            include_nw = bool(bucket_data.get("include_in_net_worth", True))
            buckets.append(
                {
                    "id": bucket_id,
                    "name": bucket_data.get("name", "New Bucket"),
                    "target_weight_pct": float(bucket_data.get("target_weight_pct", 0.0)),
                    "drift_tolerance_pct": float(bucket_data.get("drift_tolerance_pct", 3.0)),
                    "color": chosen_color,
                    "description": bucket_data.get("description", ""),
                    "rules": bucket_data.get("rules", []),
                    "include_in_rebalancing": include_reb,
                    "include_in_net_worth": include_nw,
                }
            )

        data["buckets"] = buckets
        self._write_yaml_atomic(self.config_path, data)
        return bucket_id

    def delete_bucket(self, bucket_id: str) -> bool:
        """Deletes a bucket from portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        buckets = data.get("buckets", [])
        original_count = len(buckets)
        buckets = [b for b in buckets if b.get("id") != bucket_id]
        if len(buckets) == original_count:
            return False

        data["buckets"] = buckets
        self._write_yaml_atomic(self.config_path, data)
        return True

    def load_known_accounts(self) -> list[KnownAccount]:
        """Loads user-configured known accounts and destination labels."""
        if not self.config_path.exists():
            return []
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_accounts = data.get("known_accounts", [])
        accounts: list[KnownAccount] = []
        for acc in raw_accounts:
            accounts.append(
                KnownAccount(
                    id=str(acc.get("id", "")),
                    account_number=str(acc.get("account_number", "")),
                    label=str(acc.get("label", "")),
                    account_type=str(acc.get("account_type", "CHECKING")),
                    institution=str(acc.get("institution", "")),
                )
            )
        return accounts

    def save_known_account(self, account: KnownAccount) -> None:
        """Upserts a known account in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_accounts = data.get("known_accounts", [])
        updated = False
        new_list = []
        acc_dict = {
            "id": account.id,
            "account_number": account.account_number,
            "label": account.label,
            "account_type": account.account_type,
            "institution": account.institution,
        }

        for existing in raw_accounts:
            if existing.get("id") == account.id:
                new_list.append(acc_dict)
                updated = True
            else:
                new_list.append(existing)

        if not updated:
            new_list.append(acc_dict)

        data["known_accounts"] = new_list
        self._write_yaml_atomic(self.config_path, data)

    def delete_known_account(self, account_id: str) -> None:
        """Removes a known account by id from portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_accounts = data.get("known_accounts", [])
        data["known_accounts"] = [acc for acc in raw_accounts if acc.get("id") != account_id]

        self._write_yaml_atomic(self.config_path, data)

    def load_manual_assets(self) -> list[Asset]:
        """Loads manually configured assets (e.g. Bunq savings, private real estate)."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_assets = data.get("manual_assets", [])
        assets: list[Asset] = []
        for a in raw_assets:
            ac_str = str(a.get("asset_class", "CASH")).upper()
            try:
                ac = AssetClass(ac_str)
            except ValueError:
                ac = AssetClass.CASH

            val = Money.from_val(a.get("current_value", 0.0), a.get("currency", "EUR"))
            cost_raw = a.get("cost_basis")
            cost_val = (
                Money.from_val(cost_raw, a.get("currency", "EUR")) if cost_raw is not None else None
            )
            acq_date = a.get("acquisition_date") or a.get("start_date")
            assets.append(
                Asset(
                    id=str(a.get("id", "manual")),
                    name=str(a.get("name", "Manual Asset")),
                    symbol=str(a.get("symbol", "")),
                    isin=a.get("isin"),
                    asset_class=ac,
                    current_value=val,
                    cost_basis=cost_val,
                    institution=str(a.get("institution", "Manual")),
                    currency=val.currency,
                    acquisition_date=str(acq_date) if acq_date else None,
                )
            )
        return assets

    def load_manual_liabilities(self) -> list[Liability]:
        """Loads manually configured debts/mortgages."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        raw_liabilities = data.get("manual_liabilities", [])
        liabilities: list[Liability] = []
        for item in raw_liabilities:
            lt_str = str(item.get("loan_type", "MORTGAGE")).upper()
            try:
                lt = LoanType(lt_str)
            except ValueError:
                lt = LoanType.MORTGAGE

            cur = item.get("currency", "EUR")
            bal = Money.from_val(item.get("principal_balance", 0.0), cur)
            pmt = Money.from_val(item.get("monthly_payment", 0.0), cur)
            rate = Decimal(str(item.get("interest_rate_pct", 0.0)))
            pmt_pct_raw = item.get("monthly_payment_pct")
            pmt_pct = Decimal(str(pmt_pct_raw)) if pmt_pct_raw is not None else None
            start_cap_raw = item.get("start_capital")
            start_cap = Money.from_val(start_cap_raw, cur) if start_cap_raw is not None else None
            start_date = item.get("start_date")
            end_date = item.get("end_date")
            dur_raw = item.get("duration_months")
            dur_months = int(dur_raw) if dur_raw is not None else None

            if (
                bal.amount <= Decimal("0.00")
                and start_cap
                and start_cap.amount > Decimal("0.00")
                and start_date
            ):
                est_bal, est_pmt = Liability.calculate_amortized_state(
                    start_capital=start_cap,
                    interest_rate_pct=rate,
                    start_date=str(start_date),
                    duration_months=dur_months,
                    end_date=str(end_date) if end_date else None,
                )
                bal = est_bal
                if pmt.amount <= Decimal("0.00"):
                    pmt = est_pmt

            if pmt.amount <= Decimal("0.00") and pmt_pct is not None and pmt_pct > Decimal("0.00"):
                pmt = bal * (pmt_pct / Decimal("100.0"))

            liabilities.append(
                Liability(
                    id=str(item.get("id", "manual-debt")),
                    name=str(item.get("name", "Manual Debt")),
                    loan_type=lt,
                    principal_balance=bal,
                    interest_rate_pct=rate,
                    monthly_payment=pmt,
                    monthly_payment_pct=pmt_pct,
                    start_capital=start_cap,
                    start_date=str(start_date) if start_date else None,
                    end_date=str(end_date) if end_date else None,
                    duration_months=dur_months,
                    institution=str(item.get("institution", "Manual")),
                    account_reference=str(item.get("account_reference", "")),
                )
            )
        return liabilities

    def load_transaction_rules(self) -> list[dict[str, Any]]:
        """Loads custom learned classification rules."""
        if not self.rules_path.exists():
            return []
        with open(self.rules_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or []

    def save_transaction_rule(self, rule: dict[str, Any]) -> None:
        """Appends a learned transaction classification rule."""
        rules = self.load_transaction_rules()
        # Deduplicate by pattern
        existing = next((r for r in rules if r.get("pattern") == rule.get("pattern")), None)
        if existing:
            existing.update(rule)
        else:
            rules.append(rule)

        self._write_yaml_atomic(self.rules_path, rules)

    def load_settings(self) -> dict[str, Any]:
        """Loads system settings (PDT credentials, MCP servers, AI config, Tax settings)."""
        if not self.config_path.exists():
            return {}
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        settings = data.get("settings", {})
        pdt_cfg = settings.get("pdt", {})
        # Check if pdt_auth.json or ~/.pdt_auth.json exists as fallback if not explicitly disconnected
        pdt_token_file = self.config_path.parent / "pdt_auth.json"
        home_token_file = Path.home() / ".pdt_auth.json"
        token_files = (
            (pdt_token_file, home_token_file) if self.tenant_id == "default" else (pdt_token_file,)
        )
        if pdt_cfg.get("connected") is not False and not pdt_cfg.get("auth_token"):
            for tf in token_files:
                if tf.exists():
                    try:
                        import json

                        with open(tf, encoding="utf-8") as f_tok:
                            tok_data = json.load(f_tok)
                            pdt_cfg["auth_token"] = tok_data.get("access_token")
                            pdt_cfg["refresh_token"] = tok_data.get("refresh_token")
                            pdt_cfg["client_id"] = tok_data.get("client_id")
                            pdt_cfg["expires_at"] = tok_data.get("expires_at")
                            pdt_cfg["connected"] = True
                            break
                    except Exception:
                        pass

        ai_key = settings.get("ai", {}).get("api_key")
        if isinstance(ai_key, str) and ai_key.startswith("enc:"):
            ai_key = self._get_secret_vault().decrypt(ai_key)

        pdt_token = pdt_cfg.get("auth_token")
        if isinstance(pdt_token, str) and pdt_token.startswith("enc:"):
            pdt_token = self._get_secret_vault().decrypt(pdt_token)

        # Return consolidated settings with defaults
        return {
            "pdt": {
                "mcp_url": pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com"),
                "client_id": pdt_cfg.get("client_id"),
                "auth_token": pdt_token,
                "refresh_token": pdt_cfg.get("refresh_token"),
                "expires_at": pdt_cfg.get("expires_at"),
                "connected": bool(pdt_token or pdt_cfg.get("connected")),
                "last_sync": pdt_cfg.get("last_sync"),
            },
            "mcp_servers": settings.get(
                "mcp_servers",
                [
                    {
                        "id": "pdt-official",
                        "name": "Portfolio Dividend Tracker (PDT)",
                        "url": "https://mcp.portfoliodividendtracker.com",
                        "transport": "http",
                        "auth_token": pdt_token,
                        "enabled": True,
                    }
                ],
            ),
            "ai": {
                "provider": settings.get("ai", {}).get("provider", "algorithmic"),
                "api_key": ai_key,
                "model": settings.get("ai", {}).get("model", "gemini-1.5-pro"),
                "ollama_url": settings.get("ai", {}).get("ollama_url", "http://localhost:11434"),
            },
            "tax": {
                "annual_exemption": float(settings.get("tax", {}).get("annual_exemption", 10000.0)),
                "benchmark_date": settings.get("tax", {}).get("benchmark_date", "2025-12-31"),
                "benchmark_price": float(settings.get("tax", {}).get("benchmark_price", 900.0)),
                "tax_rate_pct": float(settings.get("tax", {}).get("tax_rate_pct", 10.0)),
            },
            "cloud_sync": {
                "sync_dir": settings.get("cloud_sync", {}).get("sync_dir", ""),
                "last_backup": settings.get("cloud_sync", {}).get("last_backup"),
            },
            "language": settings.get("language", "en"),
            "regional_format": settings.get("regional_format", "auto"),
            "onboarding_complete": bool(settings.get("onboarding_complete", False)),
        }

    def save_settings(self, settings_dict: dict[str, Any]) -> None:
        """Saves or updates system settings in portfolio.yaml, preserving existing secrets if masked."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        current_settings = data.get("settings", {})

        for key, val in settings_dict.items():
            if isinstance(val, dict) and isinstance(current_settings.get(key), dict):
                merged = dict(current_settings[key])
                for sub_k, sub_v in val.items():
                    if sub_k in ("api_key", "auth_token", "refresh_token") and (
                        _is_masked_secret(sub_v) or sub_v is None or sub_v == ""
                    ):
                        # Only clear if explicitly requested via disconnect_pdt or if no previous secret existed
                        if sub_v is None and key == "pdt" or sub_k not in merged:
                            merged[sub_k] = None
                        continue
                    merged[sub_k] = sub_v
                current_settings[key] = merged
            elif isinstance(val, dict):
                cleaned = {}
                for sub_k, sub_v in val.items():
                    if sub_k in ("api_key", "auth_token", "refresh_token") and _is_masked_secret(
                        sub_v
                    ):
                        continue
                    cleaned[sub_k] = sub_v
                current_settings[key] = cleaned
            else:
                current_settings[key] = val

        data["settings"] = current_settings
        self._write_yaml_atomic(self.config_path, data)

    def save_pdt_tokens(self, tokens: dict[str, Any]) -> None:
        """Stores received PDT OAuth tokens in settings and standalone pdt_auth.json."""
        current = self.load_settings()
        pdt = current.get("pdt", {})
        pdt["auth_token"] = tokens.get("access_token")
        pdt["refresh_token"] = tokens.get("refresh_token")
        pdt["client_id"] = tokens.get("client_id")
        pdt["expires_at"] = tokens.get("expires_at")
        pdt["connected"] = True

        self.save_settings({"pdt": pdt})

        # Also write to local token cache for compatibility with PDT-TUI
        try:
            import json

            pdt_token_file = self.config_path.parent / "pdt_auth.json"
            with open(pdt_token_file, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2)
            _secure_file_perms(pdt_token_file)
        except Exception:
            pass

    def disconnect_pdt(self) -> None:
        """Disconnects PDT MCP integration and clears stored tokens."""
        current = self.load_settings()
        pdt = current.get("pdt", {})
        pdt["auth_token"] = None
        pdt["refresh_token"] = None
        pdt["connected"] = False
        self.save_settings({"pdt": pdt})

        pdt_token_file = self.config_path.parent / "pdt_auth.json"
        if pdt_token_file.exists():
            with contextlib.suppress(Exception):
                pdt_token_file.unlink()

    def add_mcp_server(self, server: dict[str, Any]) -> None:
        """Registers a new custom MCP server."""
        current = self.load_settings()
        servers = current.get("mcp_servers", [])
        # Check if already exists
        existing = next((s for s in servers if s.get("id") == server.get("id")), None)
        if existing:
            existing.update(server)
        else:
            servers.append(server)
        self.save_settings({"mcp_servers": servers})

    def delete_mcp_server(self, server_id: str) -> None:
        """Removes a custom MCP server by ID."""
        current = self.load_settings()
        servers = [s for s in current.get("mcp_servers", []) if s.get("id") != server_id]
        self.save_settings({"mcp_servers": servers})

    def update_pdt_sync_timestamp(self) -> None:
        """Updates last successful sync timestamp for PDT."""
        from datetime import datetime

        current = self.load_settings()
        pdt = current.get("pdt", {})
        pdt["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_settings({"pdt": pdt})

    def save_manual_asset(self, asset_dict: dict[str, Any]) -> None:
        """Saves or updates a manual asset in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        manual_assets = data.get("manual_assets", [])
        asset_id = str(asset_dict.get("id") or f"asset-{uuid.uuid4().hex[:8]}")
        asset_dict["id"] = asset_id

        existing = next((a for a in manual_assets if str(a.get("id")) == asset_id), None)
        if existing:
            existing.update(asset_dict)
        else:
            manual_assets.append(asset_dict)

        data["manual_assets"] = manual_assets
        self._write_yaml_atomic(self.config_path, data)

    def delete_manual_asset(self, asset_id: str) -> None:
        """Deletes a manual asset by id."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        manual_assets = [
            a for a in data.get("manual_assets", []) if str(a.get("id")) != str(asset_id)
        ]
        data["manual_assets"] = manual_assets
        self._write_yaml_atomic(self.config_path, data)

    def save_manual_liability(self, liability_dict: dict[str, Any]) -> None:
        """Saves or updates a manual liability (mortgage/loan) in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        liabilities = data.get("manual_liabilities", [])
        liability_id = str(liability_dict.get("id") or f"debt-{uuid.uuid4().hex[:8]}")
        liability_dict["id"] = liability_id

        existing = next((liab for liab in liabilities if str(liab.get("id")) == liability_id), None)
        if existing:
            existing.update(liability_dict)
        else:
            liabilities.append(liability_dict)

        data["manual_liabilities"] = liabilities
        self._write_yaml_atomic(self.config_path, data)

    def delete_manual_liability(self, liability_id: str) -> None:
        """Deletes a manual liability by id."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        liabilities = [
            liab
            for liab in data.get("manual_liabilities", [])
            if str(liab.get("id")) != str(liability_id)
        ]
        data["manual_liabilities"] = liabilities
        self._write_yaml_atomic(self.config_path, data)

    def assign_asset_to_bucket(
        self,
        bucket_id: str,
        symbol: str | None = None,
        isin: str | None = None,
        asset_id: str | None = None,
        name: str | None = None,
    ) -> None:
        """Assigns an asset to a strategic bucket by updating symbol/isin mapping rules in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        buckets = data.get("buckets", [])
        target_sym = (symbol or "").strip()
        target_isin = (isin or "").strip()

        # Remove matching symbol or ISIN from all buckets to avoid duplicate/conflicting classification
        for b in buckets:
            for rule in b.get("rules", []):
                if target_sym and "symbols" in rule:
                    rule["symbols"] = [
                        s for s in rule["symbols"] if s.upper() != target_sym.upper()
                    ]
                if target_isin and "isins" in rule:
                    rule["isins"] = [i for i in rule["isins"] if i.upper() != target_isin.upper()]

        # Assign to the target bucket if bucket_id is not empty or "unassigned"
        if bucket_id and bucket_id != "unassigned":
            target_bucket = next((b for b in buckets if b.get("id") == bucket_id), None)
            if target_bucket:
                rules = target_bucket.setdefault("rules", [])
                if not rules:
                    rules.append({})
                first_rule = rules[0]
                if target_sym:
                    syms = first_rule.setdefault("symbols", [])
                    if target_sym not in syms:
                        syms.append(target_sym)
                elif target_isin:
                    isins = first_rule.setdefault("isins", [])
                    if target_isin not in isins:
                        isins.append(target_isin)
                elif name:
                    keywords = first_rule.setdefault("name_keywords", [])
                    if name not in keywords:
                        keywords.append(name)

        data["buckets"] = buckets
        self._write_yaml_atomic(self.config_path, data)

    def load_milestones(self) -> list[dict[str, Any]]:
        """Loads configured wealth milestones."""
        if not self.config_path.exists():
            return []
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        milestones = data.get("milestones")
        if milestones is None:
            # Default milestone ladder
            milestones = [
                {
                    "id": "m1",
                    "name": "Financial Security",
                    "target_amount": 100000.0,
                    "currency": "EUR",
                },
                {
                    "id": "m2",
                    "name": "Quarter Million",
                    "target_amount": 250000.0,
                    "currency": "EUR",
                },
                {
                    "id": "m3",
                    "name": "Half Million",
                    "target_amount": 500000.0,
                    "currency": "EUR",
                },
                {
                    "id": "m4",
                    "name": "Financial Independence (€1M)",
                    "target_amount": 1000000.0,
                    "currency": "EUR",
                },
                {
                    "id": "m5",
                    "name": "Fat FIRE (€2M)",
                    "target_amount": 2000000.0,
                    "currency": "EUR",
                },
            ]
        return milestones

    def save_milestones(self, milestones: list[dict[str, Any]]) -> None:
        """Saves wealth milestones in portfolio.yaml."""
        with open(self.config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data["milestones"] = milestones
        self._write_yaml_atomic(self.config_path, data)

    def export_raw_config(self) -> dict[str, Any]:
        """Exports portfolio.yaml and rules.yaml dictionaries for encrypted vault backups."""
        portfolio_data: dict[str, Any] = {}
        if self.config_path.exists():
            with open(self.config_path, encoding="utf-8") as f:
                portfolio_data = yaml.safe_load(f) or {}
        rules_data: list[dict[str, Any]] = []
        if self.rules_path.exists():
            with open(self.rules_path, encoding="utf-8") as f:
                rules_data = yaml.safe_load(f) or []
        return {
            "portfolio": portfolio_data,
            "rules": rules_data,
        }

    def import_raw_config(self, config_bundle: dict[str, Any]) -> None:
        """Restores portfolio.yaml and rules.yaml from decrypted vault backup."""
        if "portfolio" in config_bundle and isinstance(config_bundle["portfolio"], dict):
            self._write_yaml_atomic(self.config_path, config_bundle["portfolio"])
        if "rules" in config_bundle and isinstance(config_bundle["rules"], list):
            self._write_yaml_atomic(self.rules_path, config_bundle["rules"])
