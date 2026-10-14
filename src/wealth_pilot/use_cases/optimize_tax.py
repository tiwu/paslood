"""Use Case: Optimize Tax & Belgian Capital Gains Exemption."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from wealth_pilot.domain.money import Money


class OptimizeTaxUseCase:
    """Calculates capital gains tax liabilities and optimizes annual exemptions."""

    def calculate_capital_gains_tax(
        self,
        shares_to_sell: Decimal,
        current_price: Money,
        benchmark_price: Money | None = None,
        peildatum_price: Money | None = None,
        shares_pre_benchmark: Decimal | None = None,
        shares_post_benchmark: Decimal = Decimal("0.0"),
        actual_purchase_price: Money | None = None,
        available_annual_exemption: Money | None = None,
        tax_rate_pct: Decimal = Decimal("10.0"),
    ) -> dict[str, Any]:
        bench_p = (benchmark_price or peildatum_price or Money.from_val(0.0)).amount
        curr_p = current_price.amount
        exemption = (
            available_annual_exemption.amount
            if available_annual_exemption is not None
            else Decimal("10000.00")
        )

        if shares_pre_benchmark is None:
            sold_pre = max(Decimal("0.0"), shares_to_sell - shares_post_benchmark)
            sold_post = min(shares_post_benchmark, max(Decimal("0.0"), shares_to_sell - sold_pre))
        else:
            sold_pre = min(shares_pre_benchmark, shares_to_sell)
            sold_post = min(shares_post_benchmark, max(Decimal("0.0"), shares_to_sell - sold_pre))

        # 1. Pre-benchmark shares: cost basis is the Dec 31, 2025 benchmark price
        gain_per_pre = max(Decimal("0.00"), curr_p - bench_p)
        gain_pre = (sold_pre * gain_per_pre).quantize(Decimal("0.01"))

        # 2. Post-benchmark shares: cost basis is the actual purchase price
        actual_p = actual_purchase_price.amount if actual_purchase_price is not None else curr_p
        gain_per_post = max(Decimal("0.00"), curr_p - actual_p)
        gain_post = (sold_post * gain_per_post).quantize(Decimal("0.01"))

        total_taxable_gain = (gain_pre + gain_post).quantize(Decimal("0.01"))

        used_exemption = min(total_taxable_gain, exemption).quantize(Decimal("0.01"))
        remaining_exemption = max(Decimal("0.00"), exemption - total_taxable_gain).quantize(
            Decimal("0.01")
        )
        taxable_above_exemption = max(Decimal("0.00"), total_taxable_gain - exemption).quantize(
            Decimal("0.01")
        )

        tax_to_pay = (taxable_above_exemption * (tax_rate_pct / Decimal("100.0"))).quantize(
            Decimal("0.01")
        )

        return {
            "shares_to_sell": shares_to_sell,
            "shares_pre_benchmark": shares_pre_benchmark,
            "shares_post_benchmark": shares_post_benchmark,
            "gain_pre_benchmark": Money(gain_pre, current_price.currency),
            "gain_post_benchmark": Money(gain_post, current_price.currency),
            "taxable_gain": Money(total_taxable_gain, current_price.currency),
            "total_taxable_gain": Money(total_taxable_gain, current_price.currency),
            "used_exemption": Money(used_exemption, current_price.currency),
            "remaining_exemption": Money(remaining_exemption, current_price.currency),
            "tax_to_pay": Money(tax_to_pay, current_price.currency),
            "is_fully_exempt": tax_to_pay == Decimal("0.00"),
        }

    def calculate_from_lots(
        self,
        lots: list[dict[str, Any]],
        current_price: Money,
        benchmark_date: str = "2025-12-31",
        benchmark_price: Money | None = None,
        available_annual_exemption: Money | None = None,
        tax_rate_pct: Decimal = Decimal("10.0"),
    ) -> dict[str, Any]:
        """Calculates capital gains across an explicit list of purchase lots."""
        bench_p = benchmark_price or Money.from_val(0.0)
        curr_p = current_price.amount

        shares_pre = Decimal("0.0")
        shares_post = Decimal("0.0")
        total_gain_pre = Decimal("0.0")
        total_gain_post = Decimal("0.0")

        for lot in lots:
            shares = Decimal(str(lot.get("shares", 0.0)))
            p_date = str(lot.get("purchase_date", ""))
            p_price = lot.get("purchase_price")
            p_price_amt = (
                p_price.amount if isinstance(p_price, Money) else Decimal(str(p_price or 0.0))
            )

            if p_date <= benchmark_date:
                shares_pre += shares
                gain = max(Decimal("0.00"), curr_p - bench_p.amount) * shares
                total_gain_pre += gain
            else:
                shares_post += shares
                gain = max(Decimal("0.00"), curr_p - p_price_amt) * shares
                total_gain_post += gain

        total_gain = (total_gain_pre + total_gain_post).quantize(Decimal("0.01"))
        exemption = (
            available_annual_exemption.amount
            if available_annual_exemption is not None
            else Decimal("10000.00")
        )

        used_exemption = min(total_gain, exemption).quantize(Decimal("0.01"))
        remaining_exemption = max(Decimal("0.00"), exemption - total_gain).quantize(Decimal("0.01"))
        taxable_above = max(Decimal("0.00"), total_gain - exemption).quantize(Decimal("0.01"))
        tax_to_pay = (taxable_above * (tax_rate_pct / Decimal("100.0"))).quantize(Decimal("0.01"))

        return {
            "shares_pre_benchmark": shares_pre,
            "shares_post_benchmark": shares_post,
            "total_shares": shares_pre + shares_post,
            "gain_pre_benchmark": Money(
                total_gain_pre.quantize(Decimal("0.01")), current_price.currency
            ),
            "gain_post_benchmark": Money(
                total_gain_post.quantize(Decimal("0.01")), current_price.currency
            ),
            "total_taxable_gain": Money(total_gain, current_price.currency),
            "used_exemption": Money(used_exemption, current_price.currency),
            "remaining_exemption": Money(remaining_exemption, current_price.currency),
            "tax_to_pay": Money(tax_to_pay, current_price.currency),
            "is_fully_exempt": tax_to_pay == Decimal("0.00"),
        }

    # Backward compatibility alias
    calculate_asml_tax = calculate_capital_gains_tax
