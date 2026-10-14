"""FastAPI Web Dashboard Application."""

from __future__ import annotations

import copy
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
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from wealth_pilot.adapters.ai.llm_client import UniversalAIAdvisorClient
from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.kbc_csv import KbcCsvGateway
from wealth_pilot.adapters.ingestion.pdt_auth import PdtAuthManager, generate_pkce_pair
from wealth_pilot.adapters.ingestion.pdt_mcp import PdtMcpGateway
from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.domain.asset import Asset
from wealth_pilot.domain.balance_sheet import BalanceSheet, MonthlyCashflow
from wealth_pilot.domain.liability import Liability
from wealth_pilot.domain.money import Money
from wealth_pilot.use_cases.advise_ai import AdviseAiUseCase
from wealth_pilot.use_cases.advise_contribution import AdviseContributionUseCase
from wealth_pilot.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from wealth_pilot.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from wealth_pilot.use_cases.categorize_transactions import CategorizeTransactionsUseCase
from wealth_pilot.use_cases.optimize_tax import OptimizeTaxUseCase
from wealth_pilot.use_cases.project_net_worth import ProjectNetWorthUseCase


# Request Models
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
    question: str | None = None


class SettingsUpdateRequest(BaseModel):
    ai: dict[str, Any] | None = None
    tax: dict[str, Any] | None = None
    pdt: dict[str, Any] | None = None


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
    available_annual_exemption: float | None = None


def create_app(config_repo: ConfigRepository | None = None) -> FastAPI:
    app = FastAPI(
        title="Wealth Pilot", description="Strategic Wealth & Asset Allocation Guidance Platform"
    )

    base_dir = Path(__file__).parent
    static_dir = base_dir / "static"
    templates_dir = base_dir / "templates"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount built-in documentation if available
    site_dir = Path(__file__).resolve().parents[4] / "site"
    if site_dir.exists():
        app.mount("/guide", StaticFiles(directory=str(site_dir), html=True), name="guide")

    templates = Jinja2Templates(directory=str(templates_dir))

    # Core Services & State
    repo = config_repo or ConfigRepository()
    kbc_gateway = KbcCsvGateway()
    generic_gateway = GenericCsvGateway()
    pdt_gateway = PdtMcpGateway()
    alloc_calc = CalculateBucketAllocationUseCase()
    contrib_advisor = AdviseContributionUseCase()
    debt_advisor = AdviseDebtPayoffUseCase()
    net_worth_projector = ProjectNetWorthUseCase()
    categorizer = CategorizeTransactionsUseCase()
    tax_optimizer = OptimizeTaxUseCase()

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
        "kbc_cash_asset": None,
        "kbc_liabilities": [],
        "kbc_transactions": [],
        "kbc_cashflow": None,
        "generic_assets": [],
        "pdt_assets": [],
    }

    def _get_consolidated_balance_sheet() -> BalanceSheet:
        assets: list[Asset] = []
        # Manual assets (e.g. Bunq savings)
        assets.extend(repo.load_manual_assets())

        # Ingested assets
        if state["kbc_cash_asset"]:
            assets.append(state["kbc_cash_asset"])
        assets.extend(state["generic_assets"])
        assets.extend(state["pdt_assets"])

        liabilities: list[Liability] = []
        liabilities.extend(repo.load_manual_liabilities())
        liabilities.extend(state["kbc_liabilities"])

        cashflow = state["kbc_cashflow"] or MonthlyCashflow(
            monthly_income=Money.from_val(4800.0),
            fixed_costs=Money.from_val(1200.0),
            debt_payments=Money.from_val(1553.92) if liabilities else Money.from_val(0.0),
            living_expenses=Money.from_val(800.0),
        )

        return BalanceSheet(assets=assets, liabilities=liabilities, cashflow=cashflow)

    @app.get("/", response_class=HTMLResponse)
    async def index_page(request: Request):
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/api/overview")
    async def get_overview():
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)

        # Generate guidance
        advices = []
        advices.extend(
            debt_advisor.execute(
                liabilities=bs.liabilities, monthly_surplus=bs.free_monthly_cashflow
            )
        )

        # Check drift alerts
        for a in allocations:
            if a.drift_status.value == "UNDERWEIGHT":
                from wealth_pilot.domain.advice import AdviceItem, AdviceType, Priority

                advices.append(
                    AdviceItem(
                        title=f"Underweight: {a.name}",
                        message=f"{a.name} is {abs(a.diff_weight_pct):.1f}% below target. Allocate incoming surplus to buy ~€ {abs(a.diff_value):,.2f}.",
                        priority=Priority.MEDIUM,
                        advice_type=AdviceType.PORTFOLIO_DRIFT,
                        action_amount=Money(abs(a.diff_value)),
                    )
                )

        # Trajectory
        trajectory = net_worth_projector.execute(
            initial_assets=bs.total_assets,
            initial_debts=bs.total_liabilities,
            monthly_savings=bs.free_monthly_cashflow,
            annual_return_pct=Decimal("7.0"),
            years=30,
        )

        txs = state["kbc_transactions"]
        tx_data = [
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

        return {
            "net_worth_formatted": bs.net_worth.format(),
            "total_assets_formatted": bs.total_assets.format(),
            "total_liabilities_formatted": bs.total_liabilities.format(),
            "free_cashflow_formatted": bs.free_monthly_cashflow.format(),
            "debt_to_asset_ratio": float(bs.debt_to_asset_ratio),
            "savings_rate_pct": float(bs.cashflow.savings_rate_pct),
            "asset_count": len(bs.assets),
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
                }
                for a in allocations
            ],
            "advices": [
                {
                    "title": adv.title,
                    "message": adv.message,
                    "priority": adv.priority.value,
                    "advice_type": adv.advice_type.value,
                }
                for adv in advices
            ],
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
            "transactions": tx_data,
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

            state["kbc_cash_asset"] = data["cash_asset"]
            state["kbc_liabilities"] = data["discovered_liabilities"]
            state["kbc_transactions"] = categorized_txs
            state["kbc_cashflow"] = data["cashflow"]

            return {
                "status": "success",
                "account_number": data["account_number"],
                "latest_balance": data["latest_balance"].format(),
                "transaction_count": len(categorized_txs),
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
            state["generic_assets"] = assets
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
        for tx in state["kbc_transactions"]:
            if tx.id == req.transaction_id:
                tx.category = req.target_category
                break

        if req.remember_rule and req.counterparty_name:
            repo.save_transaction_rule(
                {
                    "match_field": "counterparty_name",
                    "pattern": req.counterparty_name,
                    "target_category": req.target_category,
                }
            )

        return {"status": "success"}

    @app.post("/api/ai/advise")
    async def run_ai_consultation(req: AiAdviseRequest):
        bs = _get_consolidated_balance_sheet()
        buckets = repo.load_buckets()
        allocations = alloc_calc.execute(assets=bs.assets, buckets=buckets)
        advices = debt_advisor.execute(
            liabilities=bs.liabilities, monthly_surplus=bs.free_monthly_cashflow
        )

        ai_client = UniversalAIAdvisorClient(
            provider=req.provider,
            api_key=req.api_key,
        )
        ai_use_case = AdviseAiUseCase(ai_client=ai_client)
        advice_text = await ai_use_case.execute(
            balance_sheet=bs,
            allocations=allocations,
            deterministic_advices=advices,
            user_question=req.question,
        )
        return {"advice": advice_text}

    # Settings & MCP Management Endpoints
    @app.get("/api/settings")
    async def get_settings():
        raw_settings = repo.load_settings()
        masked = copy.deepcopy(raw_settings)
        if masked.get("ai", {}).get("api_key"):
            k = masked["ai"]["api_key"]
            masked["ai"]["api_key"] = ("••••" + k[-4:]) if len(k) > 4 else "••••••••"
        if masked.get("pdt", {}).get("auth_token"):
            t = masked["pdt"]["auth_token"]
            masked["pdt"]["auth_token"] = ("••••" + t[-4:]) if len(t) > 4 else "••••••••"
        return masked

    @app.post("/api/settings")
    async def update_settings(req: SettingsUpdateRequest):
        data = req.model_dump(exclude_unset=True)
        repo.save_settings(data)
        return {"status": "success"}

    @app.get("/api/auth/pdt/connect")
    async def initiate_pdt_oauth(request: Request):
        redirect_uri = request.query_params.get("redirect_uri")
        if not redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            redirect_uri = f"{base_url}/api/auth/pdt/callback"

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
            return RedirectResponse(url="/#settings?pdt_connected=true")
        except Exception as e:
            return RedirectResponse(url=f"/#settings?pdt_error={str(e)}")

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
        return {"status": "disconnected"}

    @app.post("/api/mcp/pdt/sync")
    async def sync_pdt_holdings():
        s = repo.load_settings()
        pdt_cfg = s.get("pdt", {})
        token = pdt_cfg.get("auth_token")
        if not token:
            raise HTTPException(
                status_code=400,
                detail="PDT is not connected. Please connect via OAuth or provide an API token in Settings.",
            )
        gateway = PdtMcpGateway(
            mcp_url=pdt_cfg.get("mcp_url", "https://mcp.portfoliodividendtracker.com"),
            auth_token=token,
        )
        assets = await gateway.fetch_portfolio_assets()
        state["pdt_assets"] = assets
        repo.update_pdt_sync_timestamp()
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
        start_t = time.time()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "WealthPilot/0.1.0",
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
                "clientInfo": {"name": "wealth-pilot", "version": "0.1.0"},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
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
        default_bench = Decimal(str(tax_cfg.get("benchmark_price", 900.0)))
        default_exemption = Decimal(str(tax_cfg.get("annual_exemption", 10000.0)))
        default_rate = Decimal(str(tax_cfg.get("tax_rate_pct", 10.0)))

        bench_price = (
            Money.from_val(req.benchmark_price)
            if req.benchmark_price is not None
            else Money(default_bench)
        )
        exemption = (
            Money.from_val(req.available_annual_exemption)
            if req.available_annual_exemption is not None
            else Money(default_exemption)
        )
        actual_buy_p = (
            Money.from_val(req.actual_purchase_price)
            if req.actual_purchase_price is not None
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
            available_annual_exemption=exemption,
            tax_rate_pct=default_rate,
        )

        return {
            "shares_to_sell": float(res["shares_to_sell"]),
            "shares_pre_benchmark": float(res["shares_pre_benchmark"]),
            "shares_post_benchmark": float(res["shares_post_benchmark"]),
            "gain_pre_benchmark": float(res["gain_pre_benchmark"].amount),
            "gain_pre_benchmark_formatted": res["gain_pre_benchmark"].format(),
            "gain_post_benchmark": float(res["gain_post_benchmark"].amount),
            "gain_post_benchmark_formatted": res["gain_post_benchmark"].format(),
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
        }

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "wealth-pilot"}

    return app


app = create_app()
