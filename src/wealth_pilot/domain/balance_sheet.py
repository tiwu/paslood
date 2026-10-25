"""Balance Sheet, Net Worth, Cashflow, and Transaction domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from wealth_pilot.domain.asset import Asset
from wealth_pilot.domain.liability import Liability
from wealth_pilot.domain.money import Money


class TransactionCategory(StrEnum):
    INCOME = "INCOME"
    MORTGAGE = "MORTGAGE"
    DEBT_REPAYMENT = "DEBT_REPAYMENT"
    INSURANCE = "INSURANCE"
    SUBSCRIPTION = "SUBSCRIPTION"
    GROCERIES = "GROCERIES"
    LIVING_EXPENSES = "LIVING_EXPENSES"
    INVESTMENTS = "INVESTMENTS"
    SAVINGS = "SAVINGS"
    TRANSFER = "TRANSFER"
    OTHER = "OTHER"


@dataclass
class Transaction:
    """A financial transaction from a bank account, broker, or manual entry."""

    id: str
    date: str  # YYYY-MM-DD
    amount: Money
    account_id: str
    description: str
    counterparty_name: str = ""
    counterparty_iban: str = ""
    category: str = TransactionCategory.OTHER.value
    bucket_id: str | None = None
    balance_after: Money | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_inflow(self) -> bool:
        return self.amount.amount > Decimal("0")

    @property
    def is_outflow(self) -> bool:
        return self.amount.amount < Decimal("0")


@dataclass(frozen=True)
class MonthlyCashflow:
    """Consolidated monthly cashflow summary."""

    monthly_income: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    fixed_costs: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    debt_payments: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    living_expenses: Money = field(default_factory=lambda: Money(Decimal("0.00")))

    @property
    def total_outflows(self) -> Money:
        return self.fixed_costs + self.debt_payments + self.living_expenses

    @property
    def free_monthly_cashflow(self) -> Money:
        """Net surplus available for investment or accelerated debt payoff."""
        return self.monthly_income - self.total_outflows

    @property
    def savings_rate_pct(self) -> Decimal:
        """Savings rate percentage of monthly income."""
        if self.monthly_income.amount <= Decimal("0"):
            return Decimal("0.00")
        surplus = self.free_monthly_cashflow.amount
        if surplus <= Decimal("0"):
            return Decimal("0.00")
        return ((surplus / self.monthly_income.amount) * Decimal("100")).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class BalanceSheet:
    """Consolidated snapshot of all assets, liabilities, and monthly cashflow."""

    assets: list[Asset] = field(default_factory=list)
    liabilities: list[Liability] = field(default_factory=list)
    cashflow: MonthlyCashflow = field(default_factory=MonthlyCashflow)
    as_of_date: str = ""

    @property
    def total_assets(self) -> Money:
        total = sum((a.current_value.amount for a in self.assets), Decimal("0.00"))
        curr = self.assets[0].currency if self.assets else "EUR"
        return Money(total, curr)

    @property
    def total_liabilities(self) -> Money:
        total = sum((liab.principal_balance.amount for liab in self.liabilities), Decimal("0.00"))
        curr = self.liabilities[0].principal_balance.currency if self.liabilities else "EUR"
        return Money(total, curr)

    @property
    def net_worth(self) -> Money:
        return self.total_assets - self.total_liabilities

    @property
    def debt_to_asset_ratio(self) -> Decimal:
        if self.total_assets.amount <= Decimal("0"):
            return Decimal("0.00")
        return (
            (self.total_liabilities.amount / self.total_assets.amount) * Decimal("100")
        ).quantize(Decimal("0.01"))

    @property
    def free_monthly_cashflow(self) -> Money:
        return self.cashflow.free_monthly_cashflow
