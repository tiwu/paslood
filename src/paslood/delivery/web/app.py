"""FastAPI Web Application Delivery Controller for Paslood.

Clean Architecture: routes and endpoints are organized into modular APIRouters
under paslood.delivery.web.routers.
"""

from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from paslood import __version__
from paslood.adapters.ingestion.bunq_csv import BunqCsvGateway
from paslood.adapters.ingestion.generic_csv import GenericCsvGateway
from paslood.adapters.ingestion.kbc_csv import KbcCsvGateway
from paslood.adapters.ingestion.pdt_mcp import PdtMcpGateway
from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.adapters.security.secret_vault import SecretVault
from paslood.adapters.settings import AppSettings
from paslood.delivery.web.auth import AuthManager
from paslood.delivery.web.helpers import _PinnedMcpNetworkBackend  # noqa: F401 re-export
from paslood.delivery.web.routers import (
    ai_router,
    auth_router,
    ingestion_router,
    planning_router,
    portfolio_router,
    settings_router,
)
from paslood.domain.identity import TenantContext, TenantRole
from paslood.use_cases.advise_contribution import AdviseContributionUseCase
from paslood.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from paslood.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase
from paslood.use_cases.optimize_tax import OptimizeTaxUseCase
from paslood.use_cases.project_net_worth import ProjectNetWorthUseCase

logger = logging.getLogger("paslood.delivery.web")


def create_app(
    config_repo: ConfigRepository | None = None,
    local_db: LocalDbRepository | None = None,
    docs_dir: Path | None = None,
    app_settings: AppSettings | None = None,
) -> FastAPI:
    settings = app_settings or AppSettings.from_env()
    if settings.mode == "saas":
        raise ValueError(
            "SaaS mode is not supported until tenant-scoped financial storage is implemented."
        )
    auth_manager = AuthManager(settings)
    secret_vault = SecretVault(settings.secret_key)

    app = FastAPI(
        title="Paslood", description="Strategic Wealth & Asset Allocation Guidance Platform"
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
                email="local@paslood",
                role=TenantRole.OWNER,
            )
            return await call_next(request)

        cookie = request.cookies.get("wp_session")
        tenant = auth_manager.verify_session(cookie) if cookie else None

        if tenant and auth_manager.is_owner_context(tenant):
            request.state.tenant = tenant
            return await call_next(request)

        if is_public:
            request.state.tenant = TenantContext(
                tenant_id="default",
                user_id="anonymous",
                email="anon@paslood",
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
            if not origin:
                if settings.auth_mode != "none" and request.cookies.get("wp_session"):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Origin header required for authenticated mutations."},
                    )
                return await call_next(request)

            def origin_key(value: str) -> tuple[str, str, int] | None:
                parsed = urllib.parse.urlsplit(value)
                if (
                    parsed.scheme.lower() not in ("http", "https")
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.path not in ("", "/")
                    or parsed.query
                    or parsed.fragment
                ):
                    return None
                try:
                    port = parsed.port
                except ValueError:
                    return None
                effective_port = port or (443 if parsed.scheme.lower() == "https" else 80)
                return parsed.scheme.lower(), parsed.hostname.lower(), effective_port

            allowed_origins = {
                key
                for value in (str(request.base_url), *settings.trusted_origins)
                if (key := origin_key(value)) is not None
            }
            if origin_key(origin) not in allowed_origins:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-origin request blocked: origin is not trusted."},
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
  <title>Paslood Documentation</title>
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
    <h1>Paslood Documentation</h1>
    <p>The documentation site has not been pre-built in this environment.</p>
    <p>Run <code>uv run mkdocs build</code> locally, or view the online docs at <a href="https://tiwu.github.io/paslood/" target="_blank">tiwu.github.io/paslood</a>.</p>
  </div>
</body>
</html>""",
                status_code=200,
            )

    templates = Jinja2Templates(directory=str(templates_dir))

    # Core Services & State
    repo = config_repo or ConfigRepository()
    db = local_db or LocalDbRepository(db_path=repo.config_path.parent / "paslood.db")
    kbc_gateway = KbcCsvGateway()
    bunq_gateway = BunqCsvGateway()
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
    app.state.auth_manager = auth_manager
    app.state.settings = settings
    app.state.secret_vault = secret_vault
    app.state.templates = templates
    app.state.kbc_gateway = kbc_gateway
    app.state.bunq_gateway = bunq_gateway
    app.state.generic_gateway = generic_gateway
    app.state.pdt_gateway = pdt_gateway
    app.state.alloc_calc = alloc_calc
    app.state.contrib_advisor = contrib_advisor
    app.state.debt_advisor = debt_advisor
    app.state.net_worth_projector = net_worth_projector
    app.state.categorizer = categorizer
    app.state.tax_optimizer = tax_optimizer

    # Register APIRouters
    app.include_router(auth_router)
    app.include_router(portfolio_router)
    app.include_router(planning_router)
    app.include_router(ingestion_router)
    app.include_router(ai_router)
    app.include_router(settings_router)

    # Core Top-Level Routes
    @app.get("/api/version")
    async def get_version() -> dict[str, str]:
        """Return the running application version."""
        return {"version": __version__}

    @app.get("/", response_class=HTMLResponse)
    async def index_page(request: Request):
        return templates.TemplateResponse(
            request=request, name="index.html", context={"app_version": __version__}
        )

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "paslood"}

    return app


app = create_app()
