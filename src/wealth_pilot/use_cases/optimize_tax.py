"""Use Case: Optimize Tax & Belgian Fiscal Shield (2026 CGT, TOB, Reynders Art. 19bis, EquatePlus)."""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import Any

from wealth_pilot.domain.money import Money
from wealth_pilot.domain.tax_rules import (
    BELGIAN_TAX_CITATIONS,
    BrokerTaxProfile,
    TobTier,
    calculate_tob_tax,
)


class OptimizeTaxUseCase:
    """Calculates Belgian capital gains tax, TOB, Reynders tax, and EquatePlus net proceeds."""

    def calculate_capital_gains_tax(
        self,
        shares_to_sell: Decimal,
        current_price: Money,
        benchmark_price: Money | None = None,
        peildatum_price: Money | None = None,
        shares_pre_benchmark: Decimal | None = None,
        shares_post_benchmark: Decimal = Decimal("0.0"),
        actual_purchase_price: Money | None = None,
        pre_benchmark_purchase_price: Money | None = None,
        available_annual_exemption: Money | None = None,
        tax_rate_pct: Decimal = Decimal("10.0"),
        carryover_years: int = 0,
        is_joint_filing: bool = False,
        tob_tier: TobTier | str = TobTier.MID_035,
        broker_profile: BrokerTaxProfile | str = BrokerTaxProfile.BELGIAN_BROKER,
        bond_weight_pct: Decimal = Decimal("0.0"),
    ) -> dict[str, Any]:
        curr = current_price.currency
        bench_p = (benchmark_price or peildatum_price or Money.from_val(0.0)).amount
        curr_p = current_price.amount

        # Statutory historical loss protection (WIB 92):
        # For pre-2026 shares, cost basis is max(Dec 31 2025 benchmark, historical purchase price)
        hist_pre_p = (
            pre_benchmark_purchase_price.amount
            if pre_benchmark_purchase_price is not None
            else Decimal("0.00")
        )
        effective_pre_basis = max(bench_p, hist_pre_p)

        # Effective Annual Exemption:
        # Base €10,000 + up to 5 years carryover (€1,000/yr -> max €15,000), doubled if joint filing
        clamped_carryover = max(0, min(5, int(carryover_years)))
        if available_annual_exemption is not None:
            base_exemption = available_annual_exemption.amount
        else:
            base_exemption = Decimal("10000.00")

        carried_exemption = base_exemption + (Decimal("1000.00") * Decimal(clamped_carryover))
        filing_multiplier = Decimal("2.0") if is_joint_filing else Decimal("1.0")
        effective_exemption = (carried_exemption * filing_multiplier).quantize(Decimal("0.01"))

        if shares_pre_benchmark is None:
            avail_pre = max(Decimal("0.0"), shares_to_sell - shares_post_benchmark)
            sold_pre = avail_pre
            sold_post = min(shares_post_benchmark, max(Decimal("0.0"), shares_to_sell - sold_pre))
        else:
            avail_pre = max(Decimal("0.0"), shares_pre_benchmark)
            sold_pre = min(avail_pre, shares_to_sell)
            sold_post = min(shares_post_benchmark, max(Decimal("0.0"), shares_to_sell - sold_pre))

        # 1. Pre-benchmark shares: cost basis is effective_pre_basis = max(Dec 31 2025, historical buy)
        gain_per_pre = max(Decimal("0.00"), curr_p - effective_pre_basis)
        gain_pre = (sold_pre * gain_per_pre).quantize(Decimal("0.01"))

        # Historical FMV gain (what foreign brokers like Equatex AG report on statements)
        fmv_basis_pre = hist_pre_p if hist_pre_p > Decimal("0.00") else bench_p
        hist_gain_per_pre = max(Decimal("0.00"), curr_p - fmv_basis_pre)
        historical_fmv_gain_pre = (sold_pre * hist_gain_per_pre).quantize(Decimal("0.01"))

        # 2. Post-benchmark shares: cost basis is the actual purchase price
        actual_p = actual_purchase_price.amount if actual_purchase_price is not None else curr_p
        gain_per_post = max(Decimal("0.00"), curr_p - actual_p)
        gain_post = (sold_post * gain_per_post).quantize(Decimal("0.01"))

        raw_total_gain = (gain_pre + gain_post).quantize(Decimal("0.01"))
        historical_fmv_gain = (historical_fmv_gain_pre + gain_post).quantize(Decimal("0.01"))
        fotomoment_exemption_saved = max(
            Decimal("0.00"), historical_fmv_gain - raw_total_gain
        ).quantize(Decimal("0.01"))

        # 3. Art. 19bis WIB 92 (Reynders Tax) split for funds with >10% debt claims
        clamped_bond_pct = max(Decimal("0.0"), min(Decimal("100.0"), Decimal(str(bond_weight_pct))))
        if clamped_bond_pct > Decimal("10.0"):
            bond_ratio = clamped_bond_pct / Decimal("100.0")
            reynders_taxable_gain = (raw_total_gain * bond_ratio).quantize(Decimal("0.01"))
            reynders_tax = (reynders_taxable_gain * Decimal("0.30")).quantize(Decimal("0.01"))
            total_taxable_gain = max(
                Decimal("0.00"), raw_total_gain - reynders_taxable_gain
            ).quantize(Decimal("0.01"))
        else:
            reynders_taxable_gain = Decimal("0.00")
            reynders_tax = Decimal("0.00")
            total_taxable_gain = raw_total_gain

        # 4. 2026 Meerwaardebelasting (10% above annual exemption)
        used_exemption = min(total_taxable_gain, effective_exemption).quantize(Decimal("0.01"))
        remaining_exemption = max(
            Decimal("0.00"), effective_exemption - total_taxable_gain
        ).quantize(Decimal("0.01"))
        taxable_above_exemption = max(
            Decimal("0.00"), total_taxable_gain - effective_exemption
        ).quantize(Decimal("0.01"))

        tax_to_pay = (taxable_above_exemption * (tax_rate_pct / Decimal("100.0"))).quantize(
            Decimal("0.01")
        )

        # 5. Gross Proceeds, Broker Fees (Equatex AG Zurich vs Belgian Broker), and TOB (WDRT Art. 120)
        gross_proceeds_amt = (shares_to_sell * curr_p).quantize(Decimal("0.01"))
        gross_proceeds = Money(gross_proceeds_amt, curr)
        tob_tax = calculate_tob_tax(gross_proceeds, tob_tier)

        try:
            resolved_profile = BrokerTaxProfile(str(broker_profile))
        except ValueError:
            resolved_profile = BrokerTaxProfile.BELGIAN_BROKER

        if resolved_profile == BrokerTaxProfile.EQUATEPLUS_CH:
            # Equatex AG Zurich exact fee schedule verified from settlement statement:
            # - Provisies (Broker Commission): 0.35%
            # - Zegelrechten bij verkoop (Swiss Federal Stamp Duty / Umsatzabgabe): 0.15%
            # - Belgian TOB (0.35%): NOT withheld by Equatex AG -> requires self-declaration
            broker_commission_amt = (gross_proceeds_amt * Decimal("0.0035")).quantize(
                Decimal("0.01")
            )
            foreign_stamp_amt = (gross_proceeds_amt * Decimal("0.0015")).quantize(Decimal("0.01"))
            tob_withheld = False
            broker_payout_amt = (
                gross_proceeds_amt - broker_commission_amt - foreign_stamp_amt
            ).quantize(Decimal("0.01"))
        elif resolved_profile == BrokerTaxProfile.FOREIGN_DIY:
            broker_commission_amt = Decimal("0.00")
            foreign_stamp_amt = Decimal("0.00")
            tob_withheld = False
            broker_payout_amt = gross_proceeds_amt
        else:
            broker_commission_amt = Decimal("0.00")
            foreign_stamp_amt = Decimal("0.00")
            tob_withheld = True
            broker_payout_amt = (gross_proceeds_amt - tob_tax.amount).quantize(Decimal("0.01"))

        total_tax_drag_amt = (tob_tax.amount + reynders_tax + tax_to_pay).quantize(Decimal("0.01"))
        net_proceeds_amt = (
            gross_proceeds_amt - broker_commission_amt - foreign_stamp_amt - total_tax_drag_amt
        ).quantize(Decimal("0.01"))

        # 6. Inverse Solver: Exact Maximum Shares Sold Tax-Free Under Remaining Exemption
        equity_ratio = (
            (Decimal("100.0") - clamped_bond_pct) / Decimal("100.0")
            if clamped_bond_pct > Decimal("10.0")
            else Decimal("1.0")
        )
        max_exempt_shares = self._solve_max_exempt_shares(
            avail_pre=avail_pre,
            avail_post=max(Decimal("0.0"), shares_post_benchmark),
            gain_per_pre=gain_per_pre * equity_ratio,
            gain_per_post=gain_per_post * equity_ratio,
            effective_exemption=effective_exemption,
        )
        max_exempt_whole_shares = max_exempt_shares.to_integral_value(rounding=ROUND_FLOOR)

        return {
            "shares_to_sell": shares_to_sell,
            "shares_pre_benchmark": shares_pre_benchmark,
            "shares_post_benchmark": shares_post_benchmark,
            "effective_pre_benchmark_basis": Money(effective_pre_basis, curr),
            "effective_annual_exemption": Money(effective_exemption, curr),
            "gain_pre_benchmark": Money(gain_pre, curr),
            "gain_post_benchmark": Money(gain_post, curr),
            "historical_fmv_gain": Money(historical_fmv_gain, curr),
            "fotomoment_exemption_saved": Money(fotomoment_exemption_saved, curr),
            "reynders_taxable_gain": Money(reynders_taxable_gain, curr),
            "reynders_tax": Money(reynders_tax, curr),
            "taxable_gain": Money(total_taxable_gain, curr),
            "total_taxable_gain": Money(total_taxable_gain, curr),
            "used_exemption": Money(used_exemption, curr),
            "remaining_exemption": Money(remaining_exemption, curr),
            "tax_to_pay": Money(tax_to_pay, curr),
            "is_fully_exempt": tax_to_pay == Decimal("0.00") and reynders_tax == Decimal("0.00"),
            "gross_proceeds": gross_proceeds,
            "broker_commission": Money(broker_commission_amt, curr),
            "foreign_stamp_tax": Money(foreign_stamp_amt, curr),
            "tob_tax": tob_tax,
            "tob_withheld_by_broker": tob_withheld,
            "tob_self_declaration_required": not tob_withheld and tob_tax.amount > Decimal("0.00"),
            "broker_payout_before_belgian_tax": Money(broker_payout_amt, curr),
            "total_tax_drag": Money(total_tax_drag_amt, curr),
            "net_proceeds": Money(net_proceeds_amt, curr),
            "max_tax_free_shares": max_exempt_shares,
            "max_tax_free_whole_shares": max_exempt_whole_shares,
            "legal_citations": [
                {
                    "key": c.key,
                    "title": c.title,
                    "statutory_article": c.statutory_article,
                    "summary": c.summary,
                    "official_url": c.official_url,
                }
                for c in BELGIAN_TAX_CITATIONS
            ],
        }

    def _solve_max_exempt_shares(
        self,
        avail_pre: Decimal,
        avail_post: Decimal,
        gain_per_pre: Decimal,
        gain_per_post: Decimal,
        effective_exemption: Decimal,
    ) -> Decimal:
        """Solves for the maximum FIFO shares that can be sold within effective_exemption."""
        total_avail = avail_pre + avail_post
        if effective_exemption <= Decimal("0.00"):
            return Decimal("0.00")

        rem_ex = effective_exemption
        exempt_shares = Decimal("0.00")

        # FIFO Step 1: Pre-2026 shares
        if avail_pre > Decimal("0.00"):
            if gain_per_pre <= Decimal("0.00"):
                exempt_shares += avail_pre
            else:
                max_pre = rem_ex / gain_per_pre
                if max_pre <= avail_pre:
                    return (exempt_shares + max_pre).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
                exempt_shares += avail_pre
                rem_ex = max(Decimal("0.00"), rem_ex - (avail_pre * gain_per_pre))

        # FIFO Step 2: Post-2025 shares
        if avail_post > Decimal("0.00"):
            if gain_per_post <= Decimal("0.00"):
                exempt_shares += avail_post
            else:
                max_post = rem_ex / gain_per_post
                if max_post <= avail_post:
                    return (exempt_shares + max_post).quantize(
                        Decimal("0.01"), rounding=ROUND_FLOOR
                    )
                exempt_shares += avail_post

        return total_avail.quantize(Decimal("0.01"), rounding=ROUND_FLOOR)

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
                # Statutory protection: max(benchmark_price, actual historical purchase price)
                effective_basis = max(bench_p.amount, p_price_amt)
                gain = max(Decimal("0.00"), curr_p - effective_basis) * shares
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
