"""Liability and Debt domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    monthly_payment_pct: Decimal | None = (
        None  # Optional monthly percentage of balance (e.g. Credit Card / Flex Loan)
    )
    start_capital: Money | None = None
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None  # YYYY-MM-DD
    duration_months: int | None = None
    institution: str = "Unknown"  # e.g., "KBC"
    account_reference: str = ""
    is_tax_deductible: bool = False

    def is_high_interest(self, threshold_pct: Decimal = Decimal("5.0")) -> bool:
        """Determines if the debt interest rate exceeds the hurdle threshold for investing."""
        return self.interest_rate_pct >= threshold_pct

    @property
    def effective_monthly_payment(self) -> Money:
        """Returns the monthly payment, computing from monthly_payment_pct if monthly_payment is 0."""
        if self.monthly_payment.amount > Decimal("0.00"):
            return self.monthly_payment
        if self.monthly_payment_pct is not None and self.monthly_payment_pct > Decimal("0.00"):
            return self.principal_balance * (self.monthly_payment_pct / Decimal("100.0"))
        return self.monthly_payment

    @property
    def annual_interest_cost(self) -> Money:
        """Estimated annual interest paid on current principal."""
        return self.principal_balance * (self.interest_rate_pct / Decimal("100.0"))

    @staticmethod
    def calculate_amortized_state(
        start_capital: Money,
        interest_rate_pct: Decimal,
        start_date: str,
        duration_months: int | None = None,
        end_date: str | None = None,
        as_of_date: str | None = None,
    ) -> tuple[Money, Money]:
        """Calculates (remaining_principal, monthly_payment) using standard annuity amortization."""
        if start_capital.amount <= Decimal("0.00"):
            return Money(Decimal("0.00"), start_capital.currency), Money(
                Decimal("0.00"), start_capital.currency
            )

        try:
            s_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
        except Exception:
            s_dt = datetime.now()

        if as_of_date:
            try:
                now_dt = datetime.strptime(as_of_date[:10], "%Y-%m-%d")
            except Exception:
                now_dt = datetime.now()
        else:
            now_dt = datetime.now()

        total_months = duration_months or 0
        if total_months <= 0 and end_date:
            try:
                e_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
                total_months = max(1, (e_dt.year - s_dt.year) * 12 + (e_dt.month - s_dt.month))
            except Exception:
                total_months = 240

        if total_months <= 0:
            total_months = 240

        elapsed_months = max(0, (now_dt.year - s_dt.year) * 12 + (now_dt.month - s_dt.month))
        if elapsed_months >= total_months:
            return Money(Decimal("0.00"), start_capital.currency), Money(
                Decimal("0.00"), start_capital.currency
            )

        p0 = float(start_capital.amount)
        r_annual = float(interest_rate_pct) / 100.0
        r_monthly = r_annual / 12.0
        n = int(total_months)
        k = int(elapsed_months)

        if r_monthly <= 0.0:
            pmt_val = p0 / n
            rem_val = max(0.0, p0 * (1.0 - (k / n)))
        else:
            factor_n = (1.0 + r_monthly) ** n
            factor_k = (1.0 + r_monthly) ** k
            pmt_val = p0 * (r_monthly * factor_n) / (factor_n - 1.0)
            rem_val = max(0.0, p0 * (factor_n - factor_k) / (factor_n - 1.0))

        return (
            Money.from_val(rem_val, start_capital.currency),
            Money.from_val(pmt_val, start_capital.currency),
        )
