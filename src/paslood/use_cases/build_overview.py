"""Use Case for assembling consolidated portfolio overview and trajectory."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from paslood.domain.advice import AdviceItem, AdviceType, Priority
from paslood.domain.asset import Asset
from paslood.domain.balance_sheet import BalanceSheet, Transaction
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

        known_accounts = repo.load_known_accounts()
        known_by_clean_acc = {
            "".join(ch for ch in k.account_number.upper() if ch.isalnum()): k
            for k in known_accounts
            if k.account_number
        }

        for a in db.get_discovered_assets():
            if a.id in existing_asset_ids:
                continue

            ac_val = a.asset_class.value if hasattr(a.asset_class, "value") else str(a.asset_class)
            if ac_val == "CASH":
                # Option A Cash Buffer Strategy:
                # 1. Exclude PDT Broker Cash (noisy / diverges from real balance)
                is_pdt_cash = (
                    a.id.lower().startswith("pdt-")
                    or (a.institution or "").upper().startswith("PDT")
                    or (a.name or "").strip().upper() == "CASH"
                )
                if is_pdt_cash:
                    continue

                # 2. Exclude operational CHECKING and CREDIT_CARD accounts
                clean_acc = "".join(ch for ch in (a.account_id or "").upper() if ch.isalnum())
                known_match = known_by_clean_acc.get(clean_acc) if clean_acc else None
                if known_match:
                    if known_match.account_type.upper() in ("CHECKING", "CREDIT_CARD"):
                        continue
                else:
                    # Unregistered statement cash accounts: exclude explicit checking / credit card accounts
                    id_low = a.id.lower()
                    name_low = (a.name or "").lower()
                    if (
                        "kbc-cc-" in id_low
                        or "credit card" in name_low
                        or "kredietkaart" in name_low
                        or ("kbc-checking-" in id_low and "spaarrekening" not in name_low)
                    ):
                        continue

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

    @staticmethod
    def build_cashflow_analytics(
        transactions: Sequence[Transaction],
        cashflow: Any,
    ) -> dict[str, Any]:
        """Builds Sankey flow links, monthly spending breakdown, and savings opportunities."""
        monthly_map: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: Decimal("0.00"))
        )
        category_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        inflow_total = Decimal("0.00")

        expense_categories = {
            "MORTGAGE",
            "DEBT_REPAYMENT",
            "INSURANCE",
            "TAX",
            "UTILITIES",
            "SUBSCRIPTION",
            "GROCERIES",
            "LEISURE",
            "TRANSPORT",
            "LIVING_EXPENSES",
            "OTHER",
        }
        wealth_categories = {"INVESTMENTS", "SAVINGS"}

        for tx in transactions:
            cat = (tx.category or "OTHER").upper()
            month = tx.date[:7] if tx.date and len(tx.date) >= 7 else "Unknown"
            if tx.is_inflow and cat not in ("TRANSFER", "SAVINGS"):
                inflow_total += tx.amount.amount
                monthly_map[month]["INCOME"] += tx.amount.amount
            elif tx.is_outflow:
                amt = abs(tx.amount.amount)
                if cat in expense_categories or cat in wealth_categories:
                    monthly_map[month][cat] += amt
                    category_totals[cat] += amt

        distinct_months = len(monthly_map) or 1
        months_dec = Decimal(str(distinct_months))

        # Build monthly_spending sorted chronologically
        monthly_spending: list[dict[str, Any]] = []
        for month_key in sorted(monthly_map.keys()):
            m_data = monthly_map[month_key]
            cats_dict = {
                k: float(v.quantize(Decimal("0.01")))
                for k, v in m_data.items()
                if k in expense_categories and v > Decimal("0.00")
            }
            total_exp = sum(cats_dict.values(), 0.0)
            monthly_spending.append(
                {
                    "month": month_key,
                    "income": float(
                        m_data.get("INCOME", Decimal("0.00")).quantize(Decimal("0.01"))
                    ),
                    "investments_and_savings": float(
                        (
                            m_data.get("INVESTMENTS", Decimal("0.00"))
                            + m_data.get("SAVINGS", Decimal("0.00"))
                        ).quantize(Decimal("0.01"))
                    ),
                    "total_expenses": round(total_exp, 2),
                    "categories": cats_dict,
                }
            )

        # Build Sankey flow (monthly averages)
        inc_avg = float(cashflow.monthly_income.amount)
        debt_avg = float(cashflow.debt_payments.amount)
        fixed_avg = float(cashflow.fixed_costs.amount)
        living_avg = float(cashflow.living_expenses.amount)
        invest_sav_avg = float(
            getattr(cashflow, "investments_and_savings", Money(Decimal("0.00"))).amount
        )
        unallocated_surplus = max(
            0.0, round(inc_avg - (debt_avg + fixed_avg + living_avg + invest_sav_avg), 2)
        )

        sankey_links: list[dict[str, Any]] = []
        if invest_sav_avg > 0 or unallocated_surplus > 0:
            if invest_sav_avg > 0:
                sankey_links.append(
                    {
                        "source": "Monthly Income",
                        "target": "Investments & Savings",
                        "value": round(invest_sav_avg, 2),
                        "color": "#10B981",
                    }
                )
            if unallocated_surplus > 0:
                sankey_links.append(
                    {
                        "source": "Monthly Income",
                        "target": "Unallocated Free Cashflow",
                        "value": round(unallocated_surplus, 2),
                        "color": "#06B6D4",
                    }
                )
        if debt_avg > 0:
            sankey_links.append(
                {
                    "source": "Monthly Income",
                    "target": "Debt & Mortgage",
                    "value": round(debt_avg, 2),
                    "color": "#F43F5E",
                }
            )
        if fixed_avg > 0:
            sankey_links.append(
                {
                    "source": "Monthly Income",
                    "target": "Fixed Costs (Tax, Utilities, Ins.)",
                    "value": round(fixed_avg, 2),
                    "color": "#8B5CF6",
                }
            )
        if living_avg > 0:
            sankey_links.append(
                {
                    "source": "Monthly Income",
                    "target": "Living & Discretionary",
                    "value": round(living_avg, 2),
                    "color": "#F59E0B",
                }
            )

        # Category breakdown per month
        category_monthly_averages = {
            cat: float((tot / months_dec).quantize(Decimal("0.01")))
            for cat, tot in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            if tot > Decimal("0.00")
        }

        # Savings Opportunities Analyzer (focusing on compressible discretionary categories)
        discretionary_targets = {
            "LEISURE": (
                "Leisure, Dining & Entertainment",
                Decimal("0.25"),
                "Trimming dining out & entertainment by 25%",
            ),
            "SUBSCRIPTION": (
                "Recurring Subscriptions",
                Decimal("0.30"),
                "Auditing unused streaming & app subscriptions (30%)",
            ),
            "LIVING_EXPENSES": (
                "General Living & Shopping",
                Decimal("0.15"),
                "Optimizing discretionary retail & impulse spend (15%)",
            ),
            "TRANSPORT": (
                "Transport & Fuel",
                Decimal("0.15"),
                "Optimizing fuel/charging & mobility costs (15%)",
            ),
            "GROCERIES": (
                "Groceries & Supermarket",
                Decimal("0.10"),
                "Smart meal planning & private-label staples (10%)",
            ),
            "UTILITIES": (
                "Utilities, Energy & Telecom",
                Decimal("0.10"),
                "Comparing Belgian energy/telecom tariffs (10%)",
            ),
        }

        savings_opportunities: list[dict[str, Any]] = []
        for cat_key, (label, reduction_factor, tip) in discretionary_targets.items():
            tot_val = category_totals.get(cat_key, Decimal("0.00"))
            if tot_val > Decimal("0.00"):
                monthly_avg = (tot_val / months_dec).quantize(Decimal("0.01"))
                potential_saving = (monthly_avg * reduction_factor).quantize(Decimal("0.01"))
                if potential_saving >= Decimal("5.00"):
                    savings_opportunities.append(
                        {
                            "category": cat_key,
                            "label": label,
                            "monthly_avg": float(monthly_avg),
                            "potential_monthly_savings": float(potential_saving),
                            "annual_impact": float(
                                (potential_saving * Decimal("12")).quantize(Decimal("0.01"))
                            ),
                            "tip": tip,
                        }
                    )

        savings_opportunities.sort(key=lambda x: x["potential_monthly_savings"], reverse=True)

        return {
            "sankey": {
                "monthly_income": inc_avg,
                "links": sankey_links,
            },
            "monthly_spending": monthly_spending,
            "category_monthly_averages": category_monthly_averages,
            "savings_opportunities": savings_opportunities,
        }

    def execute(
        self,
        balance_sheet: BalanceSheet,
        buckets: list[Bucket],
        configured_milestones: list[dict[str, Any]] | None = None,
        exclude_property: bool = False,
        cagr_pct: Decimal = Decimal("7.0"),
        projection_years: int = 30,
        start_year: int | None = None,
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
            start_year=start_year,
            balance_sheet=effective_bs,
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

        cf = effective_bs.cashflow
        cashflow_breakdown = {
            "monthly_income": float(cf.monthly_income.amount),
            "monthly_income_formatted": cf.monthly_income.format(),
            "fixed_costs": float(cf.fixed_costs.amount),
            "fixed_costs_formatted": cf.fixed_costs.format(),
            "debt_payments": float(cf.debt_payments.amount),
            "debt_payments_formatted": cf.debt_payments.format(),
            "living_expenses": float(cf.living_expenses.amount),
            "living_expenses_formatted": cf.living_expenses.format(),
            "investments_and_savings": float(cf.investments_and_savings.amount),
            "investments_and_savings_formatted": cf.investments_and_savings.format(),
            "total_outflows": float(cf.total_outflows.amount),
            "total_outflows_formatted": cf.total_outflows.format(),
            "free_cashflow": float(cf.free_monthly_cashflow.amount),
            "free_cashflow_formatted": cf.free_monthly_cashflow.format(),
            "savings_rate_pct": float(cf.savings_rate_pct),
            "months_analyzed": cf.months_analyzed,
            "is_default_estimate": cf.is_default_estimate,
            "formula": "Avg Monthly Income − (Fixed Costs + Debt Payments + Living Expenses) = Monthly Free Cashflow",
        }

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
            "cashflow_breakdown": cashflow_breakdown,
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
