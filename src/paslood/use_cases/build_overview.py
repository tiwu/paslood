"""Use Case for assembling consolidated portfolio overview and trajectory."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from paslood.domain.advice import AdviceItem, AdviceType, Priority
from paslood.domain.asset import Asset
from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.bucket import Bucket
from paslood.domain.liability import Liability
from paslood.domain.money import Money
from paslood.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from paslood.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from paslood.use_cases.ports import PortfolioRepository, TransactionRepository
from paslood.use_cases.project_net_worth import ProjectNetWorthUseCase


class BuildPortfolioOverviewUseCase:
    """Consolidates balance sheet, bucket allocations, debt payoff advice, and trajectory."""

    def __init__(
        self,
        alloc_calc: CalculateBucketAllocationUseCase | None = None,
        debt_advisor: AdviseDebtPayoffUseCase | None = None,
        net_worth_projector: ProjectNetWorthUseCase | None = None,
    ) -> None:
        self.alloc_calc = alloc_calc or CalculateBucketAllocationUseCase()
        self.debt_advisor = debt_advisor or AdviseDebtPayoffUseCase()
        self.net_worth_projector = net_worth_projector or ProjectNetWorthUseCase()

    @staticmethod
    def consolidate_balance_sheet(
        repo: PortfolioRepository, db: TransactionRepository
    ) -> BalanceSheet:
        """Builds the consolidated BalanceSheet from manual config and discovered items in SQLite."""
        assets: list[Asset] = []
        manual_assets = repo.load_manual_assets()
        assets.extend(manual_assets)
        existing_asset_ids = {a.id for a in manual_assets}

        for a in db.get_discovered_assets():
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
                existing_liab_ids.add(liab.id)
                if liab.account_reference:
                    existing_liab_refs.add(liab.account_reference)

        cashflow = db.get_monthly_cashflow()
        return BalanceSheet(assets=assets, liabilities=liabilities, cashflow=cashflow)

    def execute(
        self,
        balance_sheet: BalanceSheet,
        buckets: list[Bucket],
        configured_milestones: list[dict[str, Any]] | None = None,
        exclude_property: bool = False,
        cagr_pct: Decimal = Decimal("7.0"),
        projection_years: int = 30,
    ) -> dict[str, Any]:
        effective_bs = balance_sheet.with_effective_assets(
            buckets=buckets, exclude_property=exclude_property
        )
        allocations = self.alloc_calc.execute(assets=effective_bs.assets, buckets=buckets)

        advices: list[AdviceItem] = []
        advices.extend(
            self.debt_advisor.execute(
                liabilities=balance_sheet.liabilities,
                monthly_surplus=balance_sheet.free_monthly_cashflow,
            )
        )

        for a in allocations:
            if getattr(a.drift_status, "value", str(a.drift_status)) == "UNDERWEIGHT":
                advices.append(
                    AdviceItem(
                        title=f"Underweight: {a.name}",
                        message=f"{a.name} is {abs(a.diff_weight_pct):.1f}% below target. Allocate incoming surplus to buy ~€ {abs(a.diff_value):,.2f}.",
                        priority=Priority.MEDIUM,
                        advice_type=AdviceType.PORTFOLIO_DRIFT,
                        action_amount=Money(abs(a.diff_value)),
                    )
                )

        trajectory = self.net_worth_projector.execute(
            initial_assets=effective_bs.total_assets,
            initial_debts=effective_bs.total_liabilities,
            monthly_savings=effective_bs.free_monthly_cashflow,
            annual_return_pct=cagr_pct,
            years=projection_years,
        )

        asset_list = []
        for a in balance_sheet.assets:
            matched_b = next((b for b in buckets if b.matches(a)), None)
            asset_list.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "symbol": a.symbol,
                    "isin": a.isin,
                    "asset_class": (
                        a.asset_class.value
                        if hasattr(a.asset_class, "value")
                        else str(a.asset_class)
                    ),
                    "current_value": float(a.current_value.amount),
                    "current_value_formatted": a.current_value.format(),
                    "institution": a.institution,
                    "bucket_id": matched_b.id if matched_b else "unassigned",
                    "bucket_name": matched_b.name if matched_b else "Unassigned",
                    "bucket_color": matched_b.color if matched_b else "#64748B",
                }
            )

        liability_list = [
            {
                "id": liab.id,
                "name": liab.name,
                "loan_type": (
                    liab.loan_type.value
                    if hasattr(liab.loan_type, "value")
                    else str(liab.loan_type)
                ),
                "principal_balance": float(liab.principal_balance.amount),
                "principal_balance_formatted": liab.principal_balance.format(),
                "interest_rate_pct": float(liab.interest_rate_pct),
                "monthly_payment": float(liab.effective_monthly_payment.amount),
                "monthly_payment_formatted": liab.effective_monthly_payment.format(),
                "monthly_payment_pct": (
                    float(liab.monthly_payment_pct)
                    if liab.monthly_payment_pct is not None
                    else None
                ),
                "start_capital": (
                    float(liab.start_capital.amount) if liab.start_capital is not None else None
                ),
                "start_date": liab.start_date,
                "end_date": liab.end_date,
                "duration_months": liab.duration_months,
                "institution": liab.institution,
                "account_reference": liab.account_reference,
                "is_high_interest": liab.is_high_interest(),
            }
            for liab in balance_sheet.liabilities
        ]

        nw_val = float(effective_bs.net_worth.amount)
        milestone_data = []
        for m in configured_milestones or []:
            target = float(m.get("target_amount", 0.0))
            cur = m.get("currency", "EUR")
            pct = min(100.0, max(0.0, round((nw_val / target * 100.0), 1))) if target > 0 else 100.0
            milestone_data.append(
                {
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "target_amount": target,
                    "target_formatted": (
                        f"€ {target:,.2f}" if cur == "EUR" else f"{cur} {target:,.2f}"
                    ),
                    "progress_pct": pct,
                    "is_reached": nw_val >= target,
                }
            )

        return {
            "net_worth_value": float(effective_bs.net_worth.amount),
            "net_worth_formatted": effective_bs.net_worth.format(),
            "total_assets_value": float(effective_bs.total_assets.amount),
            "total_assets_formatted": effective_bs.total_assets.format(),
            "total_liabilities_value": float(effective_bs.total_liabilities.amount),
            "total_liabilities_formatted": effective_bs.total_liabilities.format(),
            "free_cashflow_value": float(effective_bs.free_monthly_cashflow.amount),
            "free_cashflow_formatted": effective_bs.free_monthly_cashflow.format(),
            "debt_to_asset_ratio": float(effective_bs.debt_to_asset_ratio),
            "savings_rate_pct": float(effective_bs.cashflow.savings_rate_pct),
            "asset_count": len(effective_bs.assets),
            "exclude_property": exclude_property,
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
                    "include_in_net_worth": getattr(a, "include_in_net_worth", True),
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
            "assets": asset_list,
            "liabilities": liability_list,
            "milestones": milestone_data,
        }
