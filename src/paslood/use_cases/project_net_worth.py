"""Use Case: Project Compound Net Worth and Milestones."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from paslood.domain.liability import Liability
from paslood.domain.money import Money

if TYPE_CHECKING:
    from paslood.domain.asset import Asset
    from paslood.domain.balance_sheet import BalanceSheet


class ProjectNetWorthUseCase:
    """Simulates long-term wealth accumulation and debt amortization trajectories."""

    def execute(
        self,
        initial_assets: Money,
        initial_debts: Money,
        monthly_savings: Money,
        annual_return_pct: Decimal = Decimal("7.0"),
        annual_debt_paydown: Money | None = None,
        years: int = 30,
        start_year: int | None = None,
        current_year: int | None = None,
        balance_sheet: BalanceSheet | None = None,
    ) -> list[dict[str, Any]]:
        trajectory: list[dict[str, Any]] = []

        now_yr = current_year or datetime.now().year
        effective_start_yr = min(start_year, now_yr) if start_year is not None else now_yr

        curr_assets = initial_assets.amount
        curr_debts = initial_debts.amount
        monthly_contrib = monthly_savings.amount
        annual_contrib = monthly_contrib * Decimal("12.0")
        rate = annual_return_pct / Decimal("100.0")

        # Annual amortization estimate (assume debts pay off linearly over 20 years or 5% per year)
        debt_paydown = (
            annual_debt_paydown.amount
            if annual_debt_paydown
            else (curr_debts / Decimal("20.0") if curr_debts > Decimal("0") else Decimal("0.00"))
        )

        # 1. Historical timeline (effective_start_yr to now_yr - 1)
        if effective_start_yr < now_yr:
            for past_yr in range(effective_start_yr, now_yr):
                hist_assets, hist_debts = self._estimate_historical_state(
                    year=past_yr,
                    current_year=now_yr,
                    current_assets=curr_assets,
                    current_debts=curr_debts,
                    annual_return_pct=annual_return_pct,
                    debt_paydown=debt_paydown,
                    balance_sheet=balance_sheet,
                )
                hist_nw = hist_assets - hist_debts
                trajectory.append(
                    {
                        "year": past_yr - now_yr,
                        "calendar_year": past_yr,
                        "assets": hist_assets.quantize(Decimal("0.01")),
                        "debts": hist_debts.quantize(Decimal("0.01")),
                        "net_worth": hist_nw.quantize(Decimal("0.01")),
                        "is_historical": True,
                        "is_current": False,
                        "milestones": self._detect_milestones(hist_nw),
                    }
                )

        # 2. Present day (now_yr, relative year = 0)
        curr_nw = curr_assets - curr_debts
        trajectory.append(
            {
                "year": 0,
                "calendar_year": now_yr,
                "assets": curr_assets.quantize(Decimal("0.01")),
                "debts": curr_debts.quantize(Decimal("0.01")),
                "net_worth": curr_nw.quantize(Decimal("0.01")),
                "is_historical": False,
                "is_current": True,
                "milestones": self._detect_milestones(curr_nw),
            }
        )

        # 3. Future extrapolation (1 to years)
        future_assets = curr_assets
        future_debts = curr_debts
        for yr in range(1, years + 1):
            future_assets = future_assets + (future_assets * rate) + annual_contrib
            future_debts = max(Decimal("0.00"), future_debts - debt_paydown)
            net_worth = future_assets - future_debts
            trajectory.append(
                {
                    "year": yr,
                    "calendar_year": now_yr + yr,
                    "assets": future_assets.quantize(Decimal("0.01")),
                    "debts": future_debts.quantize(Decimal("0.01")),
                    "net_worth": net_worth.quantize(Decimal("0.01")),
                    "is_historical": False,
                    "is_current": False,
                    "milestones": self._detect_milestones(net_worth),
                }
            )

        return trajectory

    def _estimate_historical_state(
        self,
        year: int,
        current_year: int,
        current_assets: Decimal,
        current_debts: Decimal,
        annual_return_pct: Decimal,
        debt_paydown: Decimal,
        balance_sheet: BalanceSheet | None,
    ) -> tuple[Decimal, Decimal]:
        if balance_sheet is not None:
            total_debt = Decimal("0.00")
            for liab in balance_sheet.liabilities:
                total_debt += self._estimate_liability_at_year(liab, year, current_year)

            total_asset = Decimal("0.00")
            for asset in balance_sheet.assets:
                total_asset += self._estimate_asset_at_year(
                    asset, year, current_year, annual_return_pct
                )
            return max(Decimal("0.00"), total_asset), max(Decimal("0.00"), total_debt)

        years_back = Decimal(str(current_year - year))
        rate = annual_return_pct / Decimal("100.0")
        growth_factor = (Decimal("1.0") + rate) ** years_back
        backcast_assets = (
            current_assets / growth_factor if growth_factor > Decimal("0") else Decimal("0.00")
        )
        backcast_debts = current_debts + (debt_paydown * years_back)
        return max(Decimal("0.00"), backcast_assets), max(Decimal("0.00"), backcast_debts)

    def _estimate_liability_at_year(self, liab: Liability, year: int, current_year: int) -> Decimal:
        as_of = f"{year}-12-31"
        if liab.start_date:
            try:
                start_yr = int(liab.start_date[:4])
            except (ValueError, IndexError):
                start_yr = current_year

            if year < start_yr:
                return Decimal("0.00")

            if liab.start_capital and liab.start_capital.amount > Decimal("0.00"):
                amortized_bal, _ = Liability.calculate_amortized_state(
                    start_capital=liab.start_capital,
                    interest_rate_pct=liab.interest_rate_pct,
                    start_date=liab.start_date,
                    duration_months=liab.duration_months,
                    end_date=liab.end_date,
                    as_of_date=as_of,
                )
                return amortized_bal.amount

        years_back = Decimal(str(current_year - year))
        annual_pmt = liab.effective_monthly_payment.amount * Decimal("12.0")
        est = liab.principal_balance.amount + (annual_pmt * years_back * Decimal("0.7"))
        return max(Decimal("0.00"), est)

    def _estimate_asset_at_year(
        self, asset: Asset, year: int, current_year: int, annual_return_pct: Decimal
    ) -> Decimal:
        curr_val = asset.current_value.amount
        cost_val = (
            asset.cost_basis.amount
            if (asset.cost_basis and asset.cost_basis.amount > Decimal("0"))
            else None
        )

        if asset.acquisition_date:
            try:
                acq_yr = int(asset.acquisition_date[:4])
            except (ValueError, IndexError):
                acq_yr = current_year

            if year < acq_yr:
                return Decimal("0.00")

            if year == acq_yr and cost_val is not None:
                return cost_val

            total_span = current_year - acq_yr
            elapsed = year - acq_yr
            if total_span > 0:
                base_start = cost_val if cost_val is not None else curr_val * Decimal("0.7")
                if base_start > Decimal("0") and curr_val > Decimal("0"):
                    try:
                        ratio = float(curr_val / base_start)
                        cagr = Decimal(str(ratio ** (1.0 / float(total_span)) - 1.0))
                        val = base_start * ((Decimal("1.0") + cagr) ** Decimal(str(elapsed)))
                        return max(Decimal("0.00"), val)
                    except Exception:
                        pass
                fraction = Decimal(str(elapsed)) / Decimal(str(total_span))
                return base_start + ((curr_val - base_start) * fraction)
            return curr_val

        if cost_val is not None and cost_val > Decimal("0"):
            years_back = Decimal(str(current_year - year))
            discount = (Decimal("1.0") + (annual_return_pct / Decimal("100.0"))) ** years_back
            est = curr_val / discount if discount > Decimal("0") else cost_val
            return max(cost_val * Decimal("0.5"), est)

        years_back = Decimal(str(current_year - year))
        discount = (Decimal("1.0") + (annual_return_pct / Decimal("100.0"))) ** years_back
        return curr_val / discount if discount > Decimal("0") else Decimal("0.00")

    def _detect_milestones(self, net_worth: Decimal) -> list[str]:
        ms = []
        if net_worth >= Decimal("100000.00"):
            ms.append("€100k")
        if net_worth >= Decimal("250000.00"):
            ms.append("€250k")
        if net_worth >= Decimal("500000.00"):
            ms.append("€500k")
        if net_worth >= Decimal("1000000.00"):
            ms.append("€1M")
        return ms
