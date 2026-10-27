"""Unit tests for the legally grounded Belgian Fiscal Shield & EquatePlus/Saxo tax engine."""

from __future__ import annotations

from decimal import Decimal

from paslood.domain.money import Money
from paslood.domain.tax_rules import (
    ASML_2025_12_31_BENCHMARK_EUR,
    BELGIAN_TAX_CITATIONS,
    BrokerTaxProfile,
    TobTier,
    calculate_tob_tax,
)
from paslood.use_cases.optimize_tax import OptimizeTaxUseCase


def test_belgian_official_tax_citations_present():
    """Verify official FOD Financiën URLs and statutory articles are defined."""
    assert len(BELGIAN_TAX_CITATIONS) >= 3
    urls = [c.official_url for c in BELGIAN_TAX_CITATIONS]
    assert any("financien.belgium.be" in u and "meerwaardebelasting" in u for u in urls)
    assert any("financien.belgium.be" in u and "taks-op-beursverrichtingen" in u for u in urls)
    assert any("fisconet" in u for u in urls)
    assert Decimal("921.40") == ASML_2025_12_31_BENCHMARK_EUR


def test_tob_statutory_tiers_and_plafond_caps():
    """Verify WDRT Art. 120-126/2 TOB rates (0.12%, 0.35%, 1.32%) and statutory caps (€1300, €1600, €4000)."""
    # 1. 0.35% equity tier on €6,584.00 (4 ASML shares at €1,646) -> €23.04
    tob_asml = calculate_tob_tax(Money(Decimal("6584.00"), "EUR"), TobTier.MID_035)
    assert tob_asml == Money(Decimal("23.04"), "EUR")

    # 2. 0.35% tier cap at €1,600.00 (for transaction > €457,142.85)
    tob_capped_mid = calculate_tob_tax(Money(Decimal("600000.00"), "EUR"), TobTier.MID_035)
    assert tob_capped_mid == Money(Decimal("1600.00"), "EUR")

    # 3. 0.12% tier cap at €1,300.00 (for transaction > €1,083,333.33)
    tob_low = calculate_tob_tax(Money(Decimal("10000.00"), "EUR"), TobTier.LOW_012)
    assert tob_low == Money(Decimal("12.00"), "EUR")
    tob_capped_low = calculate_tob_tax(Money(Decimal("2000000.00"), "EUR"), TobTier.LOW_012)
    assert tob_capped_low == Money(Decimal("1300.00"), "EUR")

    # 4. 1.32% tier cap at €4,000.00 (for transaction > €303,030.30)
    tob_high = calculate_tob_tax(Money(Decimal("10000.00"), "EUR"), TobTier.HIGH_132)
    assert tob_high == Money(Decimal("132.00"), "EUR")
    tob_capped_high = calculate_tob_tax(Money(Decimal("500000.00"), "EUR"), TobTier.HIGH_132)
    assert tob_capped_high == Money(Decimal("4000.00"), "EUR")


def test_equateplus_oct_2026_real_pdf_forensic_reproduction():
    """Reproduce the exact numbers from the Oct 5, 2026 Equatex AG Zurich ASML sale confirmation."""
    uc = OptimizeTaxUseCase()
    res = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("4"),
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(ASML_2025_12_31_BENCHMARK_EUR, "EUR"),  # €921.40
        shares_pre_benchmark=Decimal("4"),
        shares_post_benchmark=Decimal("0"),
        pre_benchmark_purchase_price=Money(Decimal("271.55"), "EUR"),  # 17 Apr 2020 FMV
        broker_profile=BrokerTaxProfile.EQUATEPLUS_CH,
        tob_tier=TobTier.MID_035,
    )

    # 1. Gross sale proceeds: 4 * 1646 = 6584.00 EUR
    assert res["gross_proceeds"] == Money(Decimal("6584.00"), "EUR")

    # 2. Equatex AG Zurich deductions:
    # Provisies (0.35%): €23.04
    # Zegelrechten / Swiss Stamp Duty (0.15%): €9.88
    # Total broker deductions: €32.92 -> Netto-opbrengst wired to KBC: €6,551.08
    assert res["broker_commission"] == Money(Decimal("23.04"), "EUR")
    assert res["foreign_stamp_tax"] == Money(Decimal("9.88"), "EUR")
    assert res["broker_payout_before_belgian_tax"] == Money(Decimal("6551.08"), "EUR")

    # 3. Unwithheld Belgian TOB (0.35%): €23.04 requiring self-declaration
    assert res["tob_tax"] == Money(Decimal("23.04"), "EUR")
    assert res["tob_withheld_by_broker"] is False
    assert res["tob_self_declaration_required"] is True

    # 4. Equatex historical FMV gain vs Legal Belgian 2026 Fotomoment gain:
    # Historical FMV gain: 4 * (1646.00 - 271.55) = €5,497.80
    # Belgian 2026 taxable gain: 4 * (1646.00 - 921.40) = €2,898.40
    # Exemption saved by using 31 Dec 2025 fotomoment: €2,599.40
    assert res["historical_fmv_gain"] == Money(Decimal("5497.80"), "EUR")
    assert res["total_taxable_gain"] == Money(Decimal("2898.40"), "EUR")
    assert res["fotomoment_exemption_saved"] == Money(Decimal("2599.40"), "EUR")

    # 5. Exemption usage & €0.00 Meerwaardebelasting
    assert res["used_exemption"] == Money(Decimal("2898.40"), "EUR")
    assert res["remaining_exemption"] == Money(Decimal("7101.60"), "EUR")
    assert res["tax_to_pay"] == Money(Decimal("0.00"), "EUR")
    assert res["is_fully_exempt"] is True

    # 6. True net proceeds after paying the €23.04 Belgian TOB to FOD Financiën:
    # €6,551.08 - €23.04 = €6,528.04
    assert res["net_proceeds"] == Money(Decimal("6528.04"), "EUR")


def test_statutory_historical_loss_protection_pre_2026():
    """If pre-2026 purchase price > Dec 31, 2025 benchmark, law uses max(bench, historical_buy)."""
    uc = OptimizeTaxUseCase()
    # Bought at €1,000 in 2024; Dec 31, 2025 fotomoment was €921.40; sold in 2026 at €980.00
    res_loss = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("10"),
        current_price=Money(Decimal("980.00"), "EUR"),
        benchmark_price=Money(Decimal("921.40"), "EUR"),
        shares_pre_benchmark=Decimal("10"),
        pre_benchmark_purchase_price=Money(Decimal("1000.00"), "EUR"),
    )
    # Because actual purchase price (€1,000) > sale price (€980), taxable gain is €0.00 (not 10 * (980 - 921.40)!)
    assert res_loss["effective_pre_benchmark_basis"] == Money(Decimal("1000.00"), "EUR")
    assert res_loss["gain_pre_benchmark"] == Money(Decimal("0.00"), "EUR")
    assert res_loss["total_taxable_gain"] == Money(Decimal("0.00"), "EUR")


def test_exemption_carryover_and_joint_filing():
    """Verify €1,000/yr carryover (max 5 yrs -> €15,000) and joint filing doubling (€20,000 -> €30,000)."""
    uc = OptimizeTaxUseCase()
    # 3 years unused carryover -> €13,000 single exemption
    res_single = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("20"),
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(
            Decimal("921.40"), "EUR"
        ),  # gain/share = €724.60; 20 shares = €14,492.00
        shares_pre_benchmark=Decimal("20"),
        carryover_years=3,
        is_joint_filing=False,
    )
    assert res_single["effective_annual_exemption"] == Money(Decimal("13000.00"), "EUR")
    assert res_single["used_exemption"] == Money(Decimal("13000.00"), "EUR")
    # Taxable above €13,000 is €1,492.00 -> 10% tax = €149.20
    assert res_single["tax_to_pay"] == Money(Decimal("149.20"), "EUR")

    # Joint filing with 3 years carryover -> 2 * €13,000 = €26,000 exemption
    res_joint = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("20"),
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(Decimal("921.40"), "EUR"),
        shares_pre_benchmark=Decimal("20"),
        carryover_years=3,
        is_joint_filing=True,
    )
    assert res_joint["effective_annual_exemption"] == Money(Decimal("26000.00"), "EUR")
    assert res_joint["tax_to_pay"] == Money(Decimal("0.00"), "EUR")


def test_reynders_tax_art_19bis_wib92_split():
    """Verify Art. 19bis WIB 92 (>10% debt claims taxed at 30% with no exemption; equity portion at 10% CGT)."""
    uc = OptimizeTaxUseCase()
    # 1. Fund with 8% bonds (<= 10% threshold) -> €0 Reynders tax
    res_below = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("100"),
        current_price=Money(Decimal("120.00"), "EUR"),
        benchmark_price=Money(Decimal("100.00"), "EUR"),
        shares_pre_benchmark=Decimal("100"),
        bond_weight_pct=Decimal("8.0"),
    )
    assert res_below["reynders_tax"] == Money(Decimal("0.00"), "EUR")

    # 2. Mixed fund with 40% bonds (> 10% threshold):
    # Total gain on 100 shares = 100 * (120 - 100) = €2,000.00
    # Bond portion (40%) = €800.00 -> taxed at 30% Reynders tax = €240.00 (no €10k exemption)
    # Equity portion (60%) = €1,200.00 -> falls under €10k exemption -> €0.00 2026 CGT
    res_mixed = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("100"),
        current_price=Money(Decimal("120.00"), "EUR"),
        benchmark_price=Money(Decimal("100.00"), "EUR"),
        shares_pre_benchmark=Decimal("100"),
        bond_weight_pct=Decimal("40.0"),
    )
    assert res_mixed["reynders_taxable_gain"] == Money(Decimal("800.00"), "EUR")
    assert res_mixed["reynders_tax"] == Money(Decimal("240.00"), "EUR")
    assert res_mixed["total_taxable_gain"] == Money(Decimal("1200.00"), "EUR")
    assert res_mixed["tax_to_pay"] == Money(Decimal("0.00"), "EUR")
    assert res_mixed["total_tax_drag"] == res_mixed["reynders_tax"] + res_mixed["tob_tax"]


def test_max_tax_free_shares_solver():
    """Verify inverse solver computes exact FIFO shares to hit €10,000 exemption with €0 CGT."""
    uc = OptimizeTaxUseCase()
    # At €1,646 current price and €921.40 benchmark, gain per share is €724.60.
    # With €10,000 exemption: 10000 / 724.60 = 13.8007... shares (or 13 whole shares).
    res = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("4"),
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(Decimal("921.40"), "EUR"),
        shares_pre_benchmark=Decimal("25"),
        shares_post_benchmark=Decimal("5"),
        actual_purchase_price=Money(Decimal("1200.00"), "EUR"),
    )
    max_shares = res["max_tax_free_shares"]
    max_whole = res["max_tax_free_whole_shares"]
    assert max_whole == Decimal("13")
    assert Decimal("13.80") <= max_shares <= Decimal("13.81")

    # Selling max_whole_shares (13) must result in €0.00 tax_to_pay
    check_whole = uc.calculate_capital_gains_tax(
        shares_to_sell=max_whole,
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(Decimal("921.40"), "EUR"),
        shares_pre_benchmark=Decimal("25"),
    )
    assert check_whole["tax_to_pay"] == Money(Decimal("0.00"), "EUR")

    # Selling 14 shares (14 * 724.60 = €10,144.40) exceeds €10,000 and triggers €14.44 tax
    check_over = uc.calculate_capital_gains_tax(
        shares_to_sell=Decimal("14"),
        current_price=Money(Decimal("1646.00"), "EUR"),
        benchmark_price=Money(Decimal("921.40"), "EUR"),
        shares_pre_benchmark=Decimal("25"),
    )
    assert check_over["tax_to_pay"] == Money(Decimal("14.44"), "EUR")
