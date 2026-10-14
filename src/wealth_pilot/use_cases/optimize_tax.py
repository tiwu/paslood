"""Use Case: Optimize Tax & Belgian Capital Gains Exemption."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from wealth_pilot.domain.money import Money


class OptimizeTaxUseCase:
    """Calculates capital gains tax liabilities and optimizes annual exemptions."""

    def calculate_asml_tax(
        self,
        shares_to_sell: Decimal,
        current_price: Money,
        peildatum_price: Money,
        available_annual_exemption: Money | None = None,
        tax_rate_pct: Decimal = Decimal("10.0"),
    ) -> dict[str, Any]:
        curr_p = current_price.amount
        peil_p = peildatum_price.amount
        exemption = (
            available_annual_exemption.amount
            if available_annual_exemption is not None
            else Decimal("10000.00")
        )

        gain_per_share = max(Decimal("0.00"), curr_p - peil_p)
        total_taxable_gain = (shares_to_sell * gain_per_share).quantize(Decimal("0.01"))

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
            "gain_per_share": Money(gain_per_share, current_price.currency),
            "taxable_gain": Money(total_taxable_gain, current_price.currency),
            "used_exemption": Money(used_exemption, current_price.currency),
            "remaining_exemption": Money(remaining_exemption, current_price.currency),
            "tax_to_pay": Money(tax_to_pay, current_price.currency),
            "is_fully_exempt": tax_to_pay == Decimal("0.00"),
        }
