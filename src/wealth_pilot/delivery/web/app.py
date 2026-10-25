"""FastAPI Web Dashboard Application."""

from __future__ import annotations

import contextlib
import copy
import ipaddress
import secrets
import tempfile
import time
import urllib.parse
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from wealth_pilot import __version__
from wealth_pilot.adapters.ai.llm_client import UniversalAIAdvisorClient
from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.kbc_csv import KbcCsvGateway
from wealth_pilot.adapters.ingestion.pdt_auth import PdtAuthManager, generate_pkce_pair
from wealth_pilot.adapters.ingestion.pdt_mcp import PdtMcpGateway
from wealth_pilot.adapters.repositories.config_repo import (
    ConfigRepository,
    _is_masked_secret,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from wealth_pilot.adapters.repositories.local_db import LocalDbRepository
from wealth_pilot.adapters.security.secret_vault import SecretVault
from wealth_pilot.adapters.settings import AppSettings
from wealth_pilot.delivery.web.auth import AuthManager
from wealth_pilot.delivery.web.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    get_translations_for_locale,
)
from wealth_pilot.domain.asset import Asset
from wealth_pilot.domain.balance_sheet import BalanceSheet
from wealth_pilot.domain.identity import TenantContext, TenantRole
from wealth_pilot.domain.liability import Liability
from wealth_pilot.domain.money import Money
from wealth_pilot.use_cases.advise_ai import AdviseAiUseCase
from wealth_pilot.use_cases.advise_contribution import AdviseContributionUseCase
from wealth_pilot.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from wealth_pilot.use_cases.build_overview import BuildPortfolioOverviewUseCase
from wealth_pilot.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from wealth_pilot.use_cases.categorize_transactions import CategorizeTransactionsUseCase
from wealth_pilot.use_cases.optimize_tax import OptimizeTaxUseCase
from wealth_pilot.use_cases.project_net_worth import ProjectNetWorthUseCase


# Request Models
class ContributionAdviceRequest(BaseModel):
    deposit: float


class BucketCreateOrUpdateRequest(BaseModel):
    id: str | None = None
    name: str
    target_weight_pct: float
    color: str | None = None
    drift_tolerance_pct: float | None = 3.0
    description: str | None = None
    include_in_rebalancing: bool | None = True
    include_in_net_worth: bool | None = True


class TargetWeightRequest(BaseModel):
    bucket_id: str
    name: str
    target_weight_pct: float


class RebucketRequest(BaseModel):
    transaction_id: str
    target_category: str
    counterparty_name: str | None = None
    remember_rule: bool = False


class AiAdviseRequest(BaseModel):
    provider: str = "gemini"
    api_key: str | None = None
    model: str | None = None
    question: str | None = None


class ManualAssetRequest(BaseModel):
    id: str | None = None
    name: str
    symbol: str | None = ""
    isin: str | None = None
    asset_class: str = "REAL_ESTATE"
    current_value: float
    institution: str | None = "Manual"
    currency: str = "EUR"


class ManualLiabilityRequest(BaseModel):
    id: str | None = None
    name: str
    loan_type: str = "MORTGAGE"
    principal_balance: float = 0.0
    interest_rate_pct: float = 0.0
    monthly_payment: float = 0.0
    monthly_payment_pct: float | None = None
    start_capital: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    institution: str | None = "Manual"
    account_reference: str | None = ""
    currency: str = "EUR"


class AssignAssetRequest(BaseModel):
    bucket_id: str
    symbol: str | None = None
    isin: str | None = None
    asset_id: str | None = None
    asset_name: str | None = None


class MilestonesUpdateRequest(BaseModel):
    milestones: list[dict[str, Any]]


class SettingsUpdateRequest(BaseModel):
    ai: dict[str, Any] | None = None
    tax: dict[str, Any] | None = None
    pdt: dict[str, Any] | None = None
    language: str | None = None
    regional_format: str | None = None


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


class TaxCalculationRequest(BaseModel):
    symbol: str | None = None
    shares_to_sell: float
    current_price: float
    benchmark_price: float | None = None
    shares_pre_benchmark: float | None = None
    shares_post_benchmark: float = 0.0
    actual_purchase_price: float | None = None
    pre_benchmark_purchase_price: float | None = None
    available_annual_exemption: float | None = None
    annual_exemption: float | None = None
    tax_rate_pct: float | None = None
    carryover_years: int = 0
    is_joint_filing: bool = False
    tob_tier: str = "0.35"
    broker_profile: str = "BELGIAN_BROKER"
    bond_weight_pct: float = 0.0


class BackupExportRequest(BaseModel):
    passphrase: str


class BackupImportRequest(BaseModel):
    bundle: dict[str, Any]
    passphrase: str


class CloudSyncRequest(BaseModel):
    sync_dir: str
    passphrase: str
    action: str = "push"  # "push" or "pull"


def create_app(
    config_repo: ConfigRepository | None = None,
    local_db: LocalDbRepository | None = None,
    docs_dir: Path | None = None,
    app_settings: AppSettings | None = None,
) -> FastAPI:
    settings = app_settings or AppSettings.from_env()
    auth_manager = AuthManager(settings)
    secret_vault = SecretVault(settings.secret_key)
    pending_oauth: dict[str, Any] = {}

    app = FastAPI(
        title="Wealth Pilot", description="Strategic Wealth & Asset Allocation Guidance Platform"
    )

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none';"
        )
        return response

    @app.middleware("http")
    async def authentication_middleware(request: Request, call_next):
        path = request.url.path
        is_public = (
            path in ("/login", "/favicon.ico", "/manifest.json")
            or path.startswith(("/auth/", "/static/", "/guide"))
            or path == "/api/health"
        )
        if settings.auth_mode == "none":
            request.state.tenant = TenantContext(
                tenant_id="default",
                user_id="default",
                email="local@wealth-pilot",
                role=TenantRole.OWNER,
            )
            return await call_next(request)

        cookie = request.cookies.get("wp_session")
        tenant = auth_manager.verify_session(cookie) if cookie else None

        if tenant:
            request.state.tenant = tenant
            return await call_next(request)

        if is_public:
            request.state.tenant = TenantContext(
                tenant_id="default",
                user_id="anonymous",
                email="anon@wealth-pilot",
                role=TenantRole.VIEWER,
            )
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse(
                status_code=401, content={"detail": "Unauthorized. Please sign in."}
            )

        return RedirectResponse(url="/login")

    @app.middleware("http")
    async def local_origin_protection_middleware(request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            if origin:
                parsed_origin = urllib.parse.urlparse(origin)
                origin_host = (parsed_origin.hostname or "").lower()
                allowed_hosts = {
                    "localhost",
                    "127.0.0.1",
                    "test",
                    "testserver",
                }
                for trusted in settings.trusted_origins:
                    p = urllib.parse.urlparse(trusted)
                    if p.hostname:
                        allowed_hosts.add(p.hostname.lower())
                if request.url.hostname:
                    allowed_hosts.add(request.url.hostname.lower())
                if origin_host not in allowed_hosts:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Cross-origin request blocked: external origin not permitted."
                        },
                    )
        return await call_next(request)

    base_dir = Path(__file__).parent
    static_dir = base_dir / "static"
    templates_dir = base_dir / "templates"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount built-in documentation if available, or register fallback route
    resolved_docs = docs_dir or (Path(__file__).resolve().parents[4] / "site")
    if resolved_docs.exists() and (resolved_docs / "index.html").exists():
        app.mount("/guide", StaticFiles(directory=str(resolved_docs), html=True), name="guide")
    else:

        @app.get("/guide/{path:path}", response_class=HTMLResponse)
        @app.get("/guide", response_class=HTMLResponse)
        async def guide_fallback(path: str = ""):
            return HTMLResponse(
                """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Wealth Pilot Documentation</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { background: #1e293b; padding: 2rem; border-radius: 0.75rem; border: 1px solid #334155; max-width: 500px; text-align: center; }
    h1 { margin-top: 0; font-size: 1.5rem; color: #38bdf8; }
    code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-size: 0.9em; }
    a { color: #38bdf8; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Wealth Pilot Documentation</h1>
    <p>The documentation site has not been pre-built in this environment.</p>
    <p>Run <code>uv run mkdocs build</code> locally, or view the online docs at <a href="https://tiwu.github.io/wealth-pilot/" target="_blank">tiwu.github.io/wealth-pilot</a>.</p>
  </div>
</body>
</html>""",
                status_code=200,
            )

    templates = Jinja2Templates(directory=str(templates_dir))

    # Core Services & State
    repo = config_repo or ConfigRepository()
    db = local_db or LocalDbRepository(db_path=repo.config_path.parent / "wealth_pilot.db")
    kbc_gateway = KbcCsvGateway()
    generic_gateway = GenericCsvGateway()
    pdt_gateway = PdtMcpGateway()
    alloc_calc = CalculateBucketAllocationUseCase()
    contrib_advisor = AdviseContributionUseCase()
    debt_advisor = AdviseDebtPayoffUseCase()
    net_worth_projector = ProjectNetWorthUseCase()
    categorizer = CategorizeTransactionsUseCase()
    tax_optimizer = OptimizeTaxUseCase()

    app.state.repo = repo
    app.state.local_db = db
    app.state.kbc_gateway = kbc_gateway
    app.state.generic_gateway = generic_gateway
    app.state.pdt_gateway = pdt_gateway
    app.state.alloc_calc = alloc_calc
    app.state.contrib_advisor = contrib_advisor
    app.state.debt_advisor = debt_advisor
    app.state.net_worth_projector = net_worth_projector
    app.state.categorizer = categorizer
    app.state.tax_optimizer = tax_optimizer

    # Session State
    pending_oauth: dict[str, Any] = {}
    state: dict[str, Any] = {
        "pdt_assets": [],
    }

    def _get_consolidated_balance_sheet() -> BalanceSheet:
        assets: list[Asset] = []
        # Manual assets (e.g. Bunq savings, Real Estate)
        manual_assets = repo.load_manual_assets()
        assets.extend(manual_assets)
        existing_asset_ids = {a.id for a in manual_assets}

        # Cached discovered assets from SQLite DB
        for a in db.get_discovered_assets():
            if a.id not in existing_asset_ids:
                assets.append(a)
                existing_asset_ids.add(a.id)

        # In-memory PDT synced assets
        for a in state["pdt_assets"]:
            if a.id not in existing_asset_ids:
                assets.append(a)
                existing_asset_ids.add(a.id)

        liabilities: list[Liability] = []
        manual_liabs = repo.load_manual_liabilities()
        liabilities.extend(manual_liabs)
        existing_liab_ids = {liab.id for liab in manual_liabs}
        existing_liab_refs = {
            liab.account_reference for liab in manual_liabs if liab.account_reference
        }

        for liab in db.get_discovered_liabilities():
            if liab.id not in existing_liab_ids and (
                not liab.account_reference or liab.account_reference not in existing_liab_refs
            ):
                liabilities.append(liab)

        cashflow = db.get_monthly_cashflow()

        return BalanceSheet(assets=assets, liabilities=liabilities, cashflow=cashflow)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "has_google": settings.has_google_oauth,
                "has_github": settings.has_github_oauth,
                "has_meta": settings.has_meta_oauth,
                "has_oauth": settings.has_oauth,
                "has_password": settings.has_password,
                "error": request.query_params.get("error"),
                "message": request.query_params.get("message"),
            },
        )

    @app.post("/auth/login")
    async def local_password_login(request: Request):
        form = await request.form()
        password = str(form.get("password") or "").strip()
        client_ip = request.client.host if request.client else "127.0.0.1"
        if not auth_manager.check_rate_limit(client_ip):
            return RedirectResponse(
                url="/login?error=Too+many+failed+attempts.+Please+wait+5+minutes.",
                status_code=303,
            )
        tenant = auth_manager.authenticate_local_password(password)
        if not tenant:
            return RedirectResponse(url="/login?error=Invalid+passphrase", status_code=303)

        token = auth_manager.create_session(user_id=tenant.user_id, tenant_id=tenant.tenant_id)
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            "wp_session",
            token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,
            secure=(request.url.scheme == "https"),
        )
        return resp

    @app.get("/auth/logout")
    async def logout(request: Request):
        cookie = request.cookies.get("wp_session")
        if cookie:
            auth_manager.delete_session(cookie)
        resp = RedirectResponse(url="/login?message=Signed+out+successfully", status_code=303)
        resp.delete_cookie("wp_session")
        return resp

    @app.get("/auth/google/login")
    async def google_login(request: Request):
        if not settings.has_google_oauth:
            return RedirectResponse(url="/login?error=Google+OAuth+not+configured", status_code=303)
        state_token = secrets.token_urlsafe(16)
        pending_oauth[state_token] = {"provider": "google", "time": time.time()}
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/google/callback"
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
        }
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        return RedirectResponse(url=url, status_code=303)

    @app.get("/auth/google/callback")
    async def google_callback(request: Request):
        code = request.query_params.get("code")
        state_token = request.query_params.get("state")
        if not state_token or state_token not in pending_oauth:
            return RedirectResponse(
                url="/login?error=Invalid+or+expired+login+state", status_code=303
            )
        pending_oauth.pop(state_token, None)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/google/callback"
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            t_resp = await client.post("https://oauth2.googleapis.com/token", data=data)
            if t_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+exchange+Google+token", status_code=303
                )
            tokens = t_resp.json()
            access_tok = tokens.get("access_token")
            u_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_tok}"},
            )
            if u_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+fetch+Google+profile", status_code=303
                )
            u_info = u_resp.json()

        email = u_info.get("email", "")
        if not email or not settings.is_email_allowed(email):
            return RedirectResponse(
                url="/login?error=Email+not+authorized+on+this+server", status_code=303
            )

        sub = str(u_info.get("sub") or email)
        name = u_info.get("name") or email.split("@")[0]
        avatar = u_info.get("picture")
        user, tenant_id = auth_manager.get_or_create_user("google", sub, email, name, avatar)
        token = auth_manager.create_session(user.id, tenant_id)
        resp = RedirectResponse(url="/#dashboard", status_code=303)
        resp.set_cookie(
            "wp_session",
            token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,
            secure=(request.url.scheme == "https"),
        )
        return resp

    @app.get("/auth/github/login")
    async def github_login(request: Request):
        if not settings.has_github_oauth:
            return RedirectResponse(url="/login?error=GitHub+OAuth+not+configured", status_code=303)
        state_token = secrets.token_urlsafe(16)
        pending_oauth[state_token] = {"provider": "github", "time": time.time()}
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/github/callback"
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state_token,
        }
        url = "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)
        return RedirectResponse(url=url, status_code=303)

    @app.get("/auth/github/callback")
    async def github_callback(request: Request):
        code = request.query_params.get("code")
        state_token = request.query_params.get("state")
        if not state_token or state_token not in pending_oauth:
            return RedirectResponse(
                url="/login?error=Invalid+or+expired+login+state", status_code=303
            )
        pending_oauth.pop(state_token, None)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/github/callback"
        data = {
            "code": code,
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "redirect_uri": redirect_uri,
        }
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            t_resp = await client.post(
                "https://github.com/login/oauth/access_token", data=data, headers=headers
            )
            if t_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+exchange+GitHub+token", status_code=303
                )
            tokens = t_resp.json()
            access_tok = tokens.get("access_token")
            u_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_tok}", "User-Agent": "WealthPilot"},
            )
            if u_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+fetch+GitHub+profile", status_code=303
                )
            u_info = u_resp.json()

            email = u_info.get("email")
            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_tok}", "User-Agent": "WealthPilot"},
                )
                if emails_resp.status_code == 200:
                    for em in emails_resp.json():
                        if em.get("primary") and em.get("verified"):
                            email = em.get("email")
                            break
                        elif em.get("verified") and not email:
                            email = em.get("email")

        if not email:
            email = f"{u_info.get('login', 'github-user')}@users.noreply.github.com"

        if not settings.is_email_allowed(email):
            return RedirectResponse(
                url="/login?error=Email+not+authorized+on+this+server", status_code=303
            )

        sub = str(u_info.get("id"))
        name = u_info.get("name") or u_info.get("login") or email.split("@")[0]
        avatar = u_info.get("avatar_url")
        user, tenant_id = auth_manager.get_or_create_user("github", sub, email, name, avatar)
        token = auth_manager.create_session(user.id, tenant_id)
        resp = RedirectResponse(url="/#dashboard", status_code=303)
        resp.set_cookie(
            "wp_session",
            token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,
            secure=(request.url.scheme == "https"),
        )
        return resp

    @app.get("/auth/meta/login")
    async def meta_login(request: Request):
        if not settings.has_meta_oauth:
            return RedirectResponse(url="/login?error=Meta+OAuth+not+configured", status_code=303)
        state_token = secrets.token_urlsafe(16)
        pending_oauth[state_token] = {"provider": "meta", "time": time.time()}
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/meta/callback"
        params = {
            "client_id": settings.meta_client_id,
            "redirect_uri": redirect_uri,
            "scope": "email,public_profile",
            "state": state_token,
        }
        url = "https://www.facebook.com/v19.0/dialog/oauth?" + urllib.parse.urlencode(params)
        return RedirectResponse(url=url, status_code=303)

    @app.get("/auth/meta/callback")
    async def meta_callback(request: Request):
        code = request.query_params.get("code")
        state_token = request.query_params.get("state")
        if not state_token or state_token not in pending_oauth:
            return RedirectResponse(
                url="/login?error=Invalid+or+expired+login+state", status_code=303
            )
        pending_oauth.pop(state_token, None)
        redirect_uri = f"{str(request.base_url).rstrip('/')}/auth/meta/callback"
        params = {
            "client_id": settings.meta_client_id,
            "client_secret": settings.meta_client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            t_resp = await client.get(
                "https://graph.facebook.com/v19.0/oauth/access_token", params=params
            )
            if t_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+exchange+Meta+token", status_code=303
                )
            tokens = t_resp.json()
            access_tok = tokens.get("access_token")
            u_resp = await client.get(
                "https://graph.facebook.com/me?fields=id,name,email",
                headers={"Authorization": f"Bearer {access_tok}"},
            )
            if u_resp.is_error:
                return RedirectResponse(
                    url="/login?error=Failed+to+fetch+Meta+profile", status_code=303
                )
            u_info = u_resp.json()

        email = u_info.get("email") or f"{u_info.get('id')}@facebook.com"
        if not settings.is_email_allowed(email):
            return RedirectResponse(
                url="/login?error=Email+not+authorized+on+this+server", status_code=303
            )

        sub = str(u_info.get("id"))
        name = u_info.get("name") or "Meta User"
        user, tenant_id = auth_manager.get_or_create_user("meta", sub, email, name, None)
        token = auth_manager.create_session(user.id, tenant_id)
        resp = RedirectResponse(url="/#dashboard", status_code=303)
        resp.set_cookie(
            "wp_session",
            token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,
            secure=(request.url.scheme == "https"),
        )
        return resp

    @app.get("/api/version")
    async def get_version() -> dict[str, str]:
        """Return the running application version."""
        return {"version": __version__}

    @app.get("/", response_class=HTMLResponse)
    async def index_page(request: Request):
        return templates.TemplateResponse(
            request=request, name="index.html", context={"app_version": __version__}
        )

    @app.get("/api/overview")
    async def get_overview(request: Request, exclude_property: bool = False):
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        configured_milestones = repo.load_milestones()

        overview_builder = BuildPortfolioOverviewUseCase(
            alloc_calc=alloc_calc,
            debt_advisor=debt_advisor,
            net_worth_projector=net_worth_projector,
        )
        data = overview_builder.execute(
            balance_sheet=bs,
            buckets=buckets,
            configured_milestones=configured_milestones,
            exclude_property=exclude_property,
        )

        txs = db.get_transactions(limit=1000)
        data["transactions"] = [
            {
                "id": t.id,
                "date": t.date,
                "description": t.description,
                "counterparty_name": t.counterparty_name,
                "amount_value": float(t.amount.amount),
                "amount_formatted": t.amount.format(),
                "category": t.category,
            }
            for t in txs
        ]

        tenant = getattr(request.state, "tenant", None)
        data["current_user"] = {
            "email": tenant.email if tenant else "local@wealth-pilot",
            "tenant_id": tenant.tenant_id if tenant else "default",
            "auth_mode": settings.auth_mode,
        }
        return data

    @app.post("/api/advice/contribution")
    async def get_contribution_advice(req: ContributionAdviceRequest):
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
        orders = contrib_advisor.execute(
            deposit=Money.from_val(req.deposit),
            allocation_results=allocations,
        )
        return {
            "status": "success",
            "deposit": req.deposit,
            "orders": [
                {
                    "bucket_id": o.bucket_id,
                    "bucket_name": o.bucket_name,
                    "amount": float(o.amount.amount),
                    "amount_formatted": o.amount.format(),
                    "percentage_of_deposit": o.percentage_of_deposit,
                }
                for o in orders
            ],
        }

    @app.post("/api/ingest/kbc")
    async def ingest_kbc_file(file: UploadFile):
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            # Load custom learned classification rules
            rules = repo.load_transaction_rules()
            kbc_gateway.categorizer = CategorizeTransactionsUseCase()
            data = kbc_gateway.parse_file(tmp_path)

            # Apply learned rules
            categorized_txs = kbc_gateway.categorizer.execute(data["transactions"], rules)

            # Save to local SQLite database (merges with earlier uploads without overwriting!)
            inserted_txs = db.save_transactions(categorized_txs, source="kbc_csv")
            if data.get("cash_asset"):
                db.save_discovered_assets([data["cash_asset"]], source="kbc_csv")
            if data.get("discovered_liabilities"):
                db.save_discovered_liabilities(data["discovered_liabilities"])

            total_txs = len(db.get_transactions())

            return {
                "status": "success",
                "account_number": data["account_number"],
                "latest_balance": data["latest_balance"].format(),
                "transaction_count": len(categorized_txs),
                "new_transactions": inserted_txs,
                "total_cumulative_transactions": total_txs,
                "discovered_liabilities_count": len(data["discovered_liabilities"]),
            }
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @app.post("/api/ingest/generic")
    async def ingest_generic_csv(file: UploadFile):
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")

        suffix = Path(file.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            assets = generic_gateway.parse_assets_file(tmp_path)
            db.save_discovered_assets(assets, source="generic_csv")
            return {
                "status": "success",
                "asset_count": len(assets),
                "total_value": sum((a.current_value.amount for a in assets), Decimal("0.00")),
            }
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @app.get("/api/template/generic")
    async def download_generic_template():
        content = generic_gateway.generate_template_csv()
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="wealth_pilot_portfolio_template.csv"'
            },
        )

    # Strategic Allocation Buckets Endpoints
    @app.post("/api/buckets")
    async def add_or_update_bucket(req: BucketCreateOrUpdateRequest):
        bucket_id = repo.save_bucket(req.model_dump(exclude_unset=True))
        return {"status": "success", "bucket_id": bucket_id}

    @app.put("/api/buckets/{bucket_id}")
    async def update_bucket(bucket_id: str, req: BucketCreateOrUpdateRequest):
        data = req.model_dump(exclude_unset=True)
        data["id"] = bucket_id
        repo.save_bucket(data)
        return {"status": "success", "bucket_id": bucket_id}

    @app.delete("/api/buckets/{bucket_id}")
    async def delete_bucket(bucket_id: str):
        deleted = repo.delete_bucket(bucket_id)
        return {"status": "success", "deleted": deleted}

    @app.post("/api/buckets/target")
    async def update_bucket_target(req: TargetWeightRequest):
        repo.save_bucket_target(
            bucket_id=req.bucket_id,
            name=req.name,
            target_weight_pct=Decimal(str(req.target_weight_pct)),
        )
        return {"status": "success"}

    @app.post("/api/transactions/rebucket")
    async def rebucket_transaction(req: RebucketRequest):
        db.update_transaction_category(req.transaction_id, req.target_category)

        if req.remember_rule and req.counterparty_name:
            repo.save_transaction_rule(
                {
                    "match_field": "counterparty_name",
                    "pattern": req.counterparty_name,
                    "target_category": req.target_category,
                }
            )

        return {"status": "success"}

    @app.post("/api/data/reset-cache")
    async def reset_cached_data():
        db.clear_all_cached_data()
        return {"status": "success", "message": "All ingested CSV cache cleared"}

    @app.get("/api/ai/models")
    async def get_ai_models(
        request: Request,
        provider: str = "gemini",
        api_key: str | None = None,
    ):
        header_key = request.headers.get("X-AI-API-Key")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            header_key = header_key or auth_header.removeprefix("Bearer ").strip()

        effective_key = header_key or api_key
        if not effective_key or _is_masked_secret(effective_key):
            s = repo.load_settings()
            raw_key = s.get("ai", {}).get("api_key")
            effective_key = secret_vault.decrypt(raw_key) if raw_key else ""
        models = await UniversalAIAdvisorClient.fetch_available_models(
            provider=provider, api_key=effective_key
        )
        return {"models": models}

    @app.post("/api/ai/advise")
    async def run_ai_consultation(req: AiAdviseRequest):
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
        advices = debt_advisor.execute(
            liabilities=bs.liabilities, monthly_surplus=bs.free_monthly_cashflow
        )

        effective_key = req.api_key
        if not effective_key or _is_masked_secret(effective_key):
            s = repo.load_settings()
            raw_key = s.get("ai", {}).get("api_key")
            effective_key = secret_vault.decrypt(raw_key) if raw_key else ""

        effective_model = req.model
        if not effective_model:
            s = repo.load_settings()
            effective_model = s.get("ai", {}).get("model")

        ai_client = UniversalAIAdvisorClient(
            provider=req.provider,
            api_key=effective_key,
            model=effective_model,
        )
        ai_use_case = AdviseAiUseCase(ai_client=ai_client)
        try:
            advice_text = await ai_use_case.execute(
                balance_sheet=bs,
                allocations=allocations,
                deterministic_advices=advices,
                user_question=req.question,
            )
            return {"advice": advice_text}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Manual Assets & Liabilities Endpoints
    @app.post("/api/assets/manual")
    async def save_manual_asset(req: ManualAssetRequest):
        asset_dict = req.model_dump(exclude_unset=True)
        repo.save_manual_asset(asset_dict)
        return {"status": "success", "asset": asset_dict}

    @app.delete("/api/assets/manual/{asset_id}")
    async def delete_manual_asset(asset_id: str):
        repo.delete_manual_asset(asset_id)
        return {"status": "success"}

    def _enrich_liability_dict(req: ManualLiabilityRequest) -> dict[str, Any]:
        liab_dict = req.model_dump(exclude_unset=True)
        cur = liab_dict.get("currency", "EUR")
        bal_val = float(liab_dict.get("principal_balance", 0.0))
        pmt_val = float(liab_dict.get("monthly_payment", 0.0))
        rate_val = float(liab_dict.get("interest_rate_pct", 0.0))
        start_cap = liab_dict.get("start_capital")
        start_date = liab_dict.get("start_date")
        end_date = liab_dict.get("end_date")
        dur_months = liab_dict.get("duration_months")
        pmt_pct = liab_dict.get("monthly_payment_pct")

        if bal_val <= 0.0 and start_cap and float(start_cap) > 0.0 and start_date:
            est_bal, est_pmt = Liability.calculate_amortized_state(
                start_capital=Money.from_val(start_cap, cur),
                interest_rate_pct=Decimal(str(rate_val)),
                start_date=str(start_date),
                duration_months=int(dur_months) if dur_months is not None else None,
                end_date=str(end_date) if end_date else None,
            )
            liab_dict["principal_balance"] = float(est_bal.amount)
            bal_val = float(est_bal.amount)
            if pmt_val <= 0.0:
                liab_dict["monthly_payment"] = float(est_pmt.amount)
                pmt_val = float(est_pmt.amount)

        if pmt_val <= 0.0 and pmt_pct is not None and float(pmt_pct) > 0.0:
            liab_dict["monthly_payment"] = round(bal_val * (float(pmt_pct) / 100.0), 2)

        return liab_dict

    @app.post("/api/liabilities/manual")
    async def save_manual_liability(req: ManualLiabilityRequest):
        liab_dict = _enrich_liability_dict(req)
        repo.save_manual_liability(liab_dict)
        if req.id:
            db.update_liability(req.id, liab_dict)
        return {"status": "success", "liability": liab_dict}

    @app.put("/api/liabilities/manual/{liability_id}")
    async def update_manual_liability(liability_id: str, req: ManualLiabilityRequest):
        liab_dict = _enrich_liability_dict(req)
        liab_dict["id"] = liability_id
        repo.save_manual_liability(liab_dict)
        db.update_liability(liability_id, liab_dict)
        return {"status": "success", "liability": liab_dict}

    @app.delete("/api/liabilities/manual/{liability_id}")
    async def delete_manual_liability(liability_id: str):
        repo.delete_manual_liability(liability_id)
        db.delete_liability(liability_id)
        return {"status": "success"}

    # Asset-to-Bucket Mapping
    @app.post("/api/buckets/assign-asset")
    async def assign_asset_to_bucket(req: AssignAssetRequest):
        repo.assign_asset_to_bucket(
            bucket_id=req.bucket_id,
            symbol=req.symbol,
            isin=req.isin,
            asset_id=req.asset_id,
            name=req.asset_name,
        )
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
        return {
            "status": "success",
            "allocations": [
                {
                    "bucket_id": a.bucket_id,
                    "name": a.name,
                    "current_value": float(a.current_value),
                    "current_weight_pct": float(a.current_weight_pct),
                    "target_weight_pct": float(a.target_weight_pct),
                    "diff_value": float(a.diff_value),
                    "diff_weight_pct": float(a.diff_weight_pct),
                    "drift_status": a.drift_status.value,
                    "drift_tolerance_pct": float(a.drift_tolerance_pct),
                    "color": a.color,
                    "include_in_rebalancing": getattr(a, "include_in_rebalancing", True),
                }
                for a in allocations
            ],
        }

    # Projections & Milestones Endpoints
    @app.get("/api/projection")
    async def get_projection(
        years: int = 30,
        cagr: float = 7.0,
        annual_savings: float | None = None,
        exclude_property: bool = False,
    ):
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        effective_assets: list[Asset] = []
        for a in bs.assets:
            ac_val = a.asset_class.value if hasattr(a.asset_class, "value") else str(a.asset_class)
            matched_b = next((b for b in buckets if b.matches(a)), None)
            if exclude_property and (
                ac_val == "REAL_ESTATE"
                or (matched_b and not getattr(matched_b, "include_in_net_worth", True))
            ):
                continue
            effective_assets.append(a)
        effective_bs = BalanceSheet(
            assets=effective_assets, liabilities=bs.liabilities, cashflow=bs.cashflow
        )
        savings_money = (
            Money.from_val(annual_savings / 12.0)
            if annual_savings is not None
            else effective_bs.free_monthly_cashflow
        )
        trajectory = net_worth_projector.execute(
            initial_assets=effective_bs.total_assets,
            initial_debts=effective_bs.total_liabilities,
            monthly_savings=savings_money,
            annual_return_pct=Decimal(str(cagr)),
            years=years,
        )
        return {
            "years": years,
            "cagr": cagr,
            "trajectory": [
                {
                    "year": t["year"],
                    "assets": float(t["assets"]),
                    "debts": float(t["debts"]),
                    "net_worth": float(t["net_worth"]),
                    "milestones": t["milestones"],
                }
                for t in trajectory
            ],
        }

    @app.get("/api/milestones")
    async def get_milestones():
        return {"milestones": repo.load_milestones()}

    @app.post("/api/milestones")
    async def save_milestones(req: MilestonesUpdateRequest):
        repo.save_milestones(req.milestones)
        return {"status": "success", "milestones": req.milestones}

    # Settings & MCP Management Endpoints
    @app.get("/api/settings")
    async def get_settings():
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

    @app.post("/api/settings")
    async def update_settings(req: SettingsUpdateRequest):
        data = req.model_dump(exclude_unset=True)
        if data.get("ai", {}).get("api_key") and not _is_masked_secret(data["ai"]["api_key"]):
            data["ai"]["api_key"] = secret_vault.encrypt(data["ai"]["api_key"])
        if data.get("pdt", {}).get("auth_token") and not _is_masked_secret(
            data["pdt"]["auth_token"]
        ):
            data["pdt"]["auth_token"] = secret_vault.encrypt(data["pdt"]["auth_token"])
        repo.save_settings(data)
        return {"status": "success"}

    @app.get("/api/i18n")
    async def get_i18n_bundle():
        return {
            "supported_languages": SUPPORTED_LANGUAGES,
            "default_language": DEFAULT_LANGUAGE,
            "translations": TRANSLATIONS,
        }

    @app.get("/api/i18n/{lang}")
    async def get_i18n_lang(lang: str):
        normalized = lang.lower()[:2]
        if normalized not in SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=404, detail=f"Language '{lang}' is not supported.")
        return {
            "language": normalized,
            "translations": get_translations_for_locale(normalized),
        }

    @app.get("/api/auth/pdt/connect")
    async def initiate_pdt_oauth(request: Request):
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

        # Dynamically register client for this redirect URI with localhost/127.0.0.1 variants
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
            client_id = pdt_cfg.get("client_id") or "wealth-pilot-client"

        verifier, challenge = generate_pkce_pair()
        state_token = secrets.token_urlsafe(16)
        pending_oauth[state_token] = {
            "verifier": verifier,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
        }
        auth_url = PdtAuthManager.build_authorization_url(
            client_id, redirect_uri, state_token, challenge
        )
        return {"auth_url": auth_url, "state": state_token}

    @app.get("/api/auth/pdt/callback")
    async def pdt_oauth_callback(request: Request):
        code = request.query_params.get("code")
        state_param = request.query_params.get("state")
        oauth_session = pending_oauth.pop(state_param or "", None)
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

            # Auto-sync holdings immediately on callback!
            synced_count = 0
            try:
                pdt_cfg = repo.load_settings().get("pdt", {})
                gateway = PdtMcpGateway(
                    mcp_url=pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com"),
                    auth_token=tokens.get("access_token"),
                )
                assets = await gateway.fetch_portfolio_assets()
                state["pdt_assets"] = assets
                if assets:
                    db.delete_discovered_assets_by_source("pdt_mcp")
                    db.save_discovered_assets(assets, source="pdt_mcp")
                repo.update_pdt_sync_timestamp()
                synced_count = len(assets)
            except Exception:
                pass

            return RedirectResponse(
                url=f"/#dashboard?pdt_connected=true&synced_count={synced_count}"
            )
        except Exception as e:
            safe_err = urllib.parse.quote(str(e))
            return RedirectResponse(url=f"/#settings?pdt_error={safe_err}")

    @app.post("/api/auth/pdt/manual")
    async def save_pdt_manual_token(req: PdtManualTokenRequest):
        repo.save_pdt_tokens({"access_token": req.auth_token, "client_id": "manual"})
        if req.mcp_url:
            s = repo.load_settings()
            p = s.get("pdt", {})
            p["mcp_url"] = req.mcp_url
            repo.save_settings({"pdt": p})
        return {"status": "success"}

    @app.post("/api/auth/pdt/disconnect")
    async def disconnect_pdt():
        repo.disconnect_pdt()
        state["pdt_assets"] = []
        db.delete_discovered_assets_by_source("pdt_mcp")
        return {"status": "disconnected"}

    async def _get_valid_pdt_token(
        pdt_cfg: dict[str, Any], force_refresh: bool = False
    ) -> str | None:
        token = pdt_cfg.get("auth_token")
        refresh_tok = pdt_cfg.get("refresh_token")
        client_id = pdt_cfg.get("client_id") or "wealth-pilot-client"
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

    @app.post("/api/mcp/pdt/sync")
    async def sync_pdt_holdings():
        s = repo.load_settings()
        pdt_cfg = s.get("pdt", {})
        token = await _get_valid_pdt_token(pdt_cfg)
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
            # Attempt token refresh on 401/403
            refreshed = await _get_valid_pdt_token(pdt_cfg, force_refresh=True)
            if refreshed and refreshed != token:
                gateway = PdtMcpGateway(mcp_url=mcp_url, auth_token=refreshed)
                assets = await gateway.fetch_portfolio_assets()
            else:
                assets = []

        if assets:
            state["pdt_assets"] = assets
            db.delete_discovered_assets_by_source("pdt_mcp")
            db.save_discovered_assets(assets, source="pdt_mcp")
            repo.update_pdt_sync_timestamp()
        else:
            # Fallback to cached PDT assets in SQLite if live sync returned 0 items
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

    @app.post("/api/settings/mcp/servers")
    async def add_custom_mcp_server(req: CustomMcpServerRequest):
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

    @app.delete("/api/settings/mcp/servers/{server_id}")
    async def delete_custom_mcp_server(server_id: str):
        repo.delete_mcp_server(server_id)
        return {"status": "success"}

    @app.post("/api/settings/mcp/servers/test")
    async def test_mcp_server(req: McpTestRequest):
        parsed = urllib.parse.urlparse(req.url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL scheme: only HTTP and HTTPS are permitted.",
            )
        hostname = (parsed.hostname or "").lower()
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

        if settings.mode != "local":
            import socket

            resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
            with contextlib.suppress(Exception):
                addr_info = socket.getaddrinfo(hostname, None)
                for info in addr_info:
                    resolved_ips.append(ipaddress.ip_address(info[4][0]))
            for rip in resolved_ips:
                if (
                    rip.is_loopback
                    or rip.is_private
                    or rip.is_link_local
                    or rip.is_reserved
                    or rip.is_multicast
                ):
                    raise HTTPException(
                        status_code=403,
                        detail="Access to internal or private network endpoints is prohibited.",
                    )

        start_t = time.time()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": f"WealthPilot/{__version__}",
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
                "clientInfo": {"name": "wealth-pilot", "version": __version__},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                resp = await client.post(req.url, json=payload, headers=headers)
                latency_ms = int((time.time() - start_t) * 1000)
                return {
                    "status": "success",
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @app.get("/api/tax/lookup-price")
    async def lookup_historical_tax_price(
        symbol: str, date: str = "2025-12-31", quote_id: str | None = None
    ):
        s = repo.load_settings()
        pdt_cfg = s.get("pdt", {})
        gateway = PdtMcpGateway(
            mcp_url=pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com"),
            auth_token=pdt_cfg.get("auth_token"),
        )
        price = await gateway.lookup_historical_price(symbol=symbol, date=date, quote_id=quote_id)
        if price:
            return {
                "status": "success",
                "symbol": symbol,
                "date": date,
                "price": float(price.amount),
                "price_formatted": price.format(),
                "source": "PDT MCP",
            }
        if symbol.strip().upper().startswith("ASML") and date == "2025-12-31":
            asml_bench = Money(Decimal("921.40"), "EUR")
            return {
                "status": "success",
                "symbol": symbol,
                "date": date,
                "price": float(asml_bench.amount),
                "price_formatted": asml_bench.format(),
                "source": "Euronext Amsterdam Official Fotomoment (31 Dec 2025)",
            }
        return {
            "status": "not_found",
            "symbol": symbol,
            "date": date,
            "price": None,
            "message": f"Historical price for {symbol} on {date} not found via PDT. You can set the base price manually.",
        }

    @app.post("/api/tax/calculate")
    async def calculate_tax(req: TaxCalculationRequest):
        s = repo.load_settings()
        tax_cfg = s.get("tax", {})
        default_bench = Decimal(str(tax_cfg.get("benchmark_price", 921.40)))
        default_exemption = Decimal(str(tax_cfg.get("annual_exemption", 10000.0)))
        default_rate = Decimal(
            str(
                req.tax_rate_pct
                if req.tax_rate_pct is not None
                else tax_cfg.get("tax_rate_pct", 10.0)
            )
        )

        bench_price = (
            Money.from_val(req.benchmark_price)
            if req.benchmark_price is not None
            else Money(default_bench)
        )
        raw_exemption = (
            req.available_annual_exemption
            if req.available_annual_exemption is not None
            else req.annual_exemption
        )
        exemption = (
            Money.from_val(raw_exemption) if raw_exemption is not None else Money(default_exemption)
        )
        actual_buy_p = (
            Money.from_val(req.actual_purchase_price)
            if req.actual_purchase_price is not None
            else None
        )
        pre_buy_p = (
            Money.from_val(req.pre_benchmark_purchase_price)
            if req.pre_benchmark_purchase_price is not None
            else None
        )

        res = tax_optimizer.calculate_capital_gains_tax(
            shares_to_sell=Decimal(str(req.shares_to_sell)),
            current_price=Money.from_val(req.current_price),
            benchmark_price=bench_price,
            shares_pre_benchmark=(
                Decimal(str(req.shares_pre_benchmark))
                if req.shares_pre_benchmark is not None
                else None
            ),
            shares_post_benchmark=Decimal(str(req.shares_post_benchmark)),
            actual_purchase_price=actual_buy_p,
            pre_benchmark_purchase_price=pre_buy_p,
            available_annual_exemption=exemption,
            tax_rate_pct=default_rate,
            carryover_years=req.carryover_years,
            is_joint_filing=req.is_joint_filing,
            tob_tier=req.tob_tier,
            broker_profile=req.broker_profile,
            bond_weight_pct=Decimal(str(req.bond_weight_pct)),
        )

        return {
            "shares_to_sell": float(res["shares_to_sell"]),
            "shares_pre_benchmark": float(res["shares_pre_benchmark"] or 0.0),
            "shares_post_benchmark": float(res["shares_post_benchmark"]),
            "effective_pre_benchmark_basis": float(res["effective_pre_benchmark_basis"].amount),
            "effective_pre_benchmark_basis_formatted": res[
                "effective_pre_benchmark_basis"
            ].format(),
            "effective_annual_exemption": float(res["effective_annual_exemption"].amount),
            "effective_annual_exemption_formatted": res["effective_annual_exemption"].format(),
            "gain_pre_benchmark": float(res["gain_pre_benchmark"].amount),
            "gain_pre_benchmark_formatted": res["gain_pre_benchmark"].format(),
            "gain_post_benchmark": float(res["gain_post_benchmark"].amount),
            "gain_post_benchmark_formatted": res["gain_post_benchmark"].format(),
            "historical_fmv_gain": float(res["historical_fmv_gain"].amount),
            "historical_fmv_gain_formatted": res["historical_fmv_gain"].format(),
            "fotomoment_exemption_saved": float(res["fotomoment_exemption_saved"].amount),
            "fotomoment_exemption_saved_formatted": res["fotomoment_exemption_saved"].format(),
            "reynders_taxable_gain": float(res["reynders_taxable_gain"].amount),
            "reynders_tax": float(res["reynders_tax"].amount),
            "reynders_tax_formatted": res["reynders_tax"].format(),
            "total_taxable_gain": float(res["total_taxable_gain"].amount),
            "total_taxable_gain_formatted": res["total_taxable_gain"].format(),
            "used_exemption": float(res["used_exemption"].amount),
            "used_exemption_formatted": res["used_exemption"].format(),
            "remaining_exemption": float(res["remaining_exemption"].amount),
            "remaining_exemption_formatted": res["remaining_exemption"].format(),
            "tax_to_pay": float(res["tax_to_pay"].amount),
            "tax_due": float(res["tax_to_pay"].amount),
            "tax_to_pay_formatted": res["tax_to_pay"].format(),
            "is_fully_exempt": res["is_fully_exempt"],
            "gross_proceeds": float(res["gross_proceeds"].amount),
            "gross_proceeds_formatted": res["gross_proceeds"].format(),
            "broker_commission": float(res["broker_commission"].amount),
            "broker_commission_formatted": res["broker_commission"].format(),
            "foreign_stamp_tax": float(res["foreign_stamp_tax"].amount),
            "foreign_stamp_tax_formatted": res["foreign_stamp_tax"].format(),
            "tob_tax": float(res["tob_tax"].amount),
            "tob_tax_formatted": res["tob_tax"].format(),
            "tob_withheld_by_broker": res["tob_withheld_by_broker"],
            "tob_self_declaration_required": res["tob_self_declaration_required"],
            "broker_payout_before_belgian_tax": float(
                res["broker_payout_before_belgian_tax"].amount
            ),
            "broker_payout_before_belgian_tax_formatted": res[
                "broker_payout_before_belgian_tax"
            ].format(),
            "total_tax_drag": float(res["total_tax_drag"].amount),
            "total_tax_drag_formatted": res["total_tax_drag"].format(),
            "net_proceeds": float(res["net_proceeds"].amount),
            "net_proceeds_formatted": res["net_proceeds"].format(),
            "max_tax_free_shares": float(res["max_tax_free_shares"]),
            "max_tax_free_whole_shares": int(res["max_tax_free_whole_shares"]),
            "legal_citations": res["legal_citations"],
        }

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "wealth-pilot"}

    # Encrypted Vault Backup & Multi-Device Cloud Drive Sync Endpoints
    @app.get("/api/backup/info")
    async def get_backup_storage_info():
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

    @app.post("/api/backup/export")
    async def export_encrypted_backup(req: BackupExportRequest):
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

    @app.post("/api/backup/import")
    async def import_encrypted_backup(req: BackupImportRequest):
        try:
            decrypted = decrypt_vault_payload(req.bundle, req.passphrase)
            if "config" in decrypted:
                repo.import_raw_config(decrypted["config"])
            if "database" in decrypted:
                db.import_state_dict(decrypted["database"])
            return {"status": "success", "exported_at": decrypted.get("exported_at")}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/api/backup/cloud-sync")
    async def sync_encrypted_vault_with_cloud_folder(req: CloudSyncRequest):
        if settings.mode != "local":
            raise HTTPException(
                status_code=403,
                detail="Cloud folder sync with server filesystem paths is disabled in remote/container mode. Please use encrypted export/import in Settings.",
            )
        if not req.sync_dir or not req.sync_dir.strip():
            raise HTTPException(status_code=400, detail="Please specify a Cloud Drive folder path.")
        sync_path = Path(req.sync_dir.strip()).expanduser().resolve()
        vault_file = sync_path / "wealth_pilot_vault.wpbackup"

        try:
            if req.action == "pull":
                if not vault_file.exists():
                    raise HTTPException(
                        status_code=404,
                        detail=f"No vault file found at {vault_file}",
                    )
                import json

                with open(vault_file, encoding="utf-8") as f:
                    bundle = json.load(f)
                decrypted = decrypt_vault_payload(bundle, req.passphrase)
                if "config" in decrypted:
                    repo.import_raw_config(decrypted["config"])
                if "database" in decrypted:
                    db.import_state_dict(decrypted["database"])
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                repo.save_settings(
                    {"cloud_sync": {"sync_dir": str(sync_path), "last_backup": now_str}}
                )
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
                import json

                with open(vault_file, "w", encoding="utf-8") as f:
                    json.dump(bundle, f, indent=2)
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                repo.save_settings(
                    {"cloud_sync": {"sync_dir": str(sync_path), "last_backup": now_str}}
                )
                return {
                    "status": "success",
                    "action": "push",
                    "vault_file": str(vault_file),
                    "last_backup": now_str,
                }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    return app


app = create_app()
