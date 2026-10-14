"""Use Case: Project Compound Net Worth and Milestones."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from wealth_pilot.domain.money import Money


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
    ) -> list[dict[str, Any]]:
        trajectory: list[dict[str, Any]] = []

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

        for yr in range(years + 1):
            net_worth = curr_assets - curr_debts
            trajectory.append(
                {
                    "year": yr,
                    "assets": curr_assets.quantize(Decimal("0.01")),
                    "debts": curr_debts.quantize(Decimal("0.01")),
                    "net_worth": net_worth.quantize(Decimal("0.01")),
                    "milestones": self._detect_milestones(net_worth),
                }
            )

            # Compound forward for next year
            investment_growth = curr_assets * rate
            curr_assets = curr_assets + investment_growth + annual_contrib
            curr_debts = max(Decimal("0.00"), curr_debts - debt_paydown)

        return trajectory

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
