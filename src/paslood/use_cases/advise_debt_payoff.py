"""Use Case: Advise Debt Payoff vs Investing Strategy."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from paslood.domain.advice import AdviceItem, AdviceType, Priority
from paslood.domain.liability import Liability
from paslood.domain.money import Money


class AdviseDebtPayoffUseCase:
    """Evaluates debts against expected investment returns to advise on payoff priorities."""

    def execute(
        self,
        liabilities: Sequence[Liability],
        monthly_surplus: Money,
        expected_portfolio_return_pct: Decimal = Decimal("7.0"),
        high_interest_threshold_pct: Decimal = Decimal("5.0"),
    ) -> list[AdviceItem]:
        advices: list[AdviceItem] = []
        if not liabilities:
            advices.append(
                AdviceItem(
                    title="Debt-Free Status",
                    message="You have no active liabilities. 100% of your monthly cashflow can be invested in your strategic buckets.",
                    priority=Priority.INFO,
                    advice_type=AdviceType.GENERAL,
                )
            )
            return advices

        # Sort debts by interest rate descending (Debt Avalanche)
        sorted_by_rate = sorted(liabilities, key=lambda liab: liab.interest_rate_pct, reverse=True)

        high_rate_debts = [
            liab for liab in sorted_by_rate if liab.interest_rate_pct >= high_interest_threshold_pct
        ]
        low_rate_debts = [
            liab for liab in sorted_by_rate if liab.interest_rate_pct < high_interest_threshold_pct
        ]

        for debt in high_rate_debts:
            advices.append(
                AdviceItem(
                    title=f"Priority Debt Payoff: {debt.name}",
                    message=(
                        f"At {debt.interest_rate_pct:.2f}% APR, paying off {debt.name} gives a guaranteed, risk-free "
                        f"return of {debt.interest_rate_pct:.2f}%. We recommend directing surplus cashflow to extinguish "
                        f"its {debt.principal_balance.format()} balance before increasing voluntary investments."
                    ),
                    priority=Priority.CRITICAL
                    if debt.interest_rate_pct > Decimal("8.0")
                    else Priority.HIGH,
                    advice_type=AdviceType.DEBT_AVALANCHE,
                    action_amount=debt.principal_balance,
                )
            )

        for debt in low_rate_debts:
            advices.append(
                AdviceItem(
                    title=f"Maintain Minimums on {debt.name}",
                    message=(
                        f"{debt.name} has a low fixed borrowing cost of {debt.interest_rate_pct:.2f}% APR, which is below "
                        f"the expected long-term portfolio CAGR of {expected_portfolio_return_pct:.1f}%. Maintain required monthly "
                        f"payments ({debt.monthly_payment.format()}/mo) and allocate surplus cashflow into equity buckets."
                    ),
                    priority=Priority.LOW,
                    advice_type=AdviceType.DEBT_AVALANCHE,
                )
            )

        return advices
