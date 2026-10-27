"""Use Case: Advise Smart Contribution (Buy-Only Rebalancing)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from paslood.domain.advice import ContributionAllocation
from paslood.domain.bucket import BucketAllocationResult
from paslood.domain.money import Money


class AdviseContributionUseCase:
    """Calculates optimal distribution of an incoming cash deposit to minimize tracking error without selling."""

    def execute(
        self,
        deposit: Money,
        allocation_results: Sequence[BucketAllocationResult],
        min_allocation: Money | None = None,
    ) -> list[ContributionAllocation]:
        deposit_amt = deposit.amount
        if deposit_amt <= Decimal("0.00"):
            return []

        # Find underweight buckets (diff_value < 0) that are included in rebalancing
        underweight = [
            r
            for r in allocation_results
            if r.diff_value < Decimal("0.00") and r.include_in_rebalancing
        ]

        if not underweight:
            # If all buckets balanced or overweight, distribute by target weights of included buckets
            total_target_pct = sum(
                (
                    r.target_weight_pct
                    for r in allocation_results
                    if r.target_weight_pct > Decimal("0") and r.include_in_rebalancing
                ),
                Decimal("0.00"),
            )
            allocations: list[ContributionAllocation] = []
            for r in allocation_results:
                if (
                    r.include_in_rebalancing
                    and r.target_weight_pct > Decimal("0")
                    and total_target_pct > Decimal("0")
                ):
                    ratio = r.target_weight_pct / total_target_pct
                    share = (deposit_amt * ratio).quantize(Decimal("0.01"))
                    pct = (ratio * Decimal("100.0")).quantize(Decimal("0.01"))
                    if share > Decimal("0"):
                        allocations.append(
                            ContributionAllocation(
                                bucket_id=r.bucket_id,
                                bucket_name=r.name,
                                amount=Money(share, deposit.currency),
                                percentage_of_deposit=pct,
                            )
                        )
            return allocations

        # Allocate proportional to deficit amount: abs(diff_value)
        total_deficit = sum((abs(r.diff_value) for r in underweight), Decimal("0.00"))
        allocations: list[ContributionAllocation] = []

        for r in underweight:
            deficit = abs(r.diff_value)
            ratio = deficit / total_deficit
            share = (deposit_amt * ratio).quantize(Decimal("0.01"))
            pct = (ratio * Decimal("100.0")).quantize(Decimal("0.01"))
            if share > Decimal("0"):
                allocations.append(
                    ContributionAllocation(
                        bucket_id=r.bucket_id,
                        bucket_name=r.name,
                        amount=Money(share, deposit.currency),
                        percentage_of_deposit=pct,
                    )
                )

        return allocations
