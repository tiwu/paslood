"""FastAPI Web Dashboard Application."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from wealth_pilot.adapters.ai.llm_client import UniversalAIAdvisorClient
from wealth_pilot.adapters.ingestion.generic_csv import GenericCsvGateway
from wealth_pilot.adapters.ingestion.kbc_csv import KbcCsvGateway
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


def create_app(config_repo: ConfigRepository | None = None) -> FastAPI:
    app = FastAPI(
        title="Wealth Pilot", description="Strategic Wealth & Asset Allocation Guidance Platform"
    )

    base_dir = Path(__file__).parent
    static_dir = base_dir / "static"
    templates_dir = base_dir / "templates"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "wealth-pilot"}

    return app


app = create_app()
