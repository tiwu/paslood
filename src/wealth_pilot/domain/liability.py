"""Liability and Debt domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from wealth_pilot.domain.money import Money


class LoanType(str, Enum):
    MORTGAGE = "MORTGAGE"
    CONSUMER_LOAN = "CONSUMER_LOAN"
    STUDENT_LOAN = "STUDENT_LOAN"
    MARGIN_LOAN = "MARGIN_LOAN"
    CREDIT_CARD = "CREDIT_CARD"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Liability:
    """A financial debt, loan, or credit obligation."""

    id: str
    name: str
    loan_type: LoanType = LoanType.MORTGAGE
    principal_balance: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    interest_rate_pct: Decimal = Decimal("0.00")  # Annual percentage rate (APR)
    monthly_payment: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    institution: str = "Unknown"  # e.g., "KBC"
    account_reference: str = ""
    is_tax_deductible: bool = False

    def is_high_interest(self, threshold_pct: Decimal = Decimal("5.0")) -> bool:
        """Determines if the debt interest rate exceeds the hurdle threshold for investing."""
        return self.interest_rate_pct >= threshold_pct

    @property
    def annual_interest_cost(self) -> Money:
        """Estimated annual interest paid on current principal."""
        return self.principal_balance * (self.interest_rate_pct / Decimal("100.0"))
