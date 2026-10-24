"""Use Case: Calculate Bucket Allocation and Drift Analysis."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from wealth_pilot.domain.asset import Asset
from wealth_pilot.domain.bucket import Bucket, BucketAllocationResult, DriftStatus


class CalculateBucketAllocationUseCase:
    """Evaluates asset holdings against configured strategic buckets."""

    def execute(
        self,
        assets: Sequence[Asset],
        buckets: Sequence[Bucket],
    ) -> list[BucketAllocationResult]:
        # Map assets to buckets
        bucket_totals: dict[str, Decimal] = {b.id: Decimal("0.00") for b in buckets}
        unallocated_total = Decimal("0.00")

        for asset in assets:
            assigned = False
            for bucket in buckets:
                if bucket.matches(asset):
                    bucket_totals[bucket.id] += asset.current_value.amount
                    assigned = True
                    break
            if not assigned:
                unallocated_total += asset.current_value.amount

        # Sum portfolio value for rebalancing purposes: included buckets + unallocated
        rebalance_portfolio_value = sum(
            (bucket_totals[b.id] for b in buckets if b.include_in_rebalancing),
            unallocated_total,
        )

        results: list[BucketAllocationResult] = []

        for bucket in buckets:
            curr_val = bucket_totals.get(bucket.id, Decimal("0.00"))
            if bucket.include_in_rebalancing:
                curr_weight_pct = (
                    ((curr_val / rebalance_portfolio_value) * Decimal("100.0")).quantize(
                        Decimal("0.01")
                    )
                    if rebalance_portfolio_value > Decimal("0.00")
                    else Decimal("0.00")
                )
                target_weight_pct = bucket.target_weight_pct.quantize(Decimal("0.01"))
                target_val = (rebalance_portfolio_value * bucket.target_weight).quantize(
                    Decimal("0.01")
                )
                diff_val = (curr_val - target_val).quantize(Decimal("0.01"))
                diff_pct = (curr_weight_pct - target_weight_pct).quantize(Decimal("0.01"))

                # Determine drift status
                tolerance = bucket.drift_tolerance_pct
                if diff_pct > tolerance:
                    status = DriftStatus.OVERWEIGHT
                elif diff_pct < -tolerance:
                    status = DriftStatus.UNDERWEIGHT
                else:
                    status = DriftStatus.BALANCED
            else:
                # Excluded from rebalancing (e.g. Real Estate): does not create drift or buy/sell imbalance
                curr_weight_pct = Decimal("0.00")
                target_weight_pct = Decimal("0.00")
                target_val = curr_val
                diff_val = Decimal("0.00")
                diff_pct = Decimal("0.00")
                status = DriftStatus.BALANCED
                tolerance = Decimal("0.00")

            results.append(
                BucketAllocationResult(
                    bucket_id=bucket.id,
                    name=bucket.name,
                    current_value=curr_val.quantize(Decimal("0.01")),
                    current_weight_pct=curr_weight_pct,
                    target_weight_pct=target_weight_pct,
                    target_value=target_val,
                    diff_value=diff_val,
                    diff_weight_pct=diff_pct,
                    drift_status=status,
                    drift_tolerance_pct=tolerance,
                    color=bucket.color,
                    include_in_rebalancing=bucket.include_in_rebalancing,
                    include_in_net_worth=getattr(bucket, "include_in_net_worth", True),
                )
            )

        if unallocated_total > Decimal("0.00"):
            unalloc_pct = (
                ((unallocated_total / rebalance_portfolio_value) * Decimal("100.0")).quantize(
                    Decimal("0.01")
                )
                if rebalance_portfolio_value > Decimal("0.00")
                else Decimal("0.00")
            )
            results.append(
                BucketAllocationResult(
                    bucket_id="unallocated",
                    name="Unallocated Assets",
                    current_value=unallocated_total.quantize(Decimal("0.01")),
                    current_weight_pct=unalloc_pct,
                    target_weight_pct=Decimal("0.00"),
                    target_value=Decimal("0.00"),
                    diff_value=unallocated_total.quantize(Decimal("0.01")),
                    diff_weight_pct=unalloc_pct,
                    drift_status=DriftStatus.OVERWEIGHT,
                    drift_tolerance_pct=Decimal("0.00"),
                    color="#9CA3AF",
                    include_in_rebalancing=True,
                )
            )

        return results
