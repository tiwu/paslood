"""Belgian Statutory Tax Rules, TOB Plafonds, Reynders Tax, and Official Citations.

Pure Python domain module (zero external framework imports).
All rates, caps, and cost-basis rules are grounded in official Belgian tax legislation:
1. Meerwaardebelasting (10% / €10,000 exemption / 31 Dec 2025 fotomoment):
   - Wetboek van de Inkomstenbelastingen 1992 (WIB 92), Art. 90, eerste lid, 9° & Art. 101-102.
   - https://financien.belgium.be/nl/particulieren/belastingen/inkomstenbelastingen/meerwaardebelasting
2. Taks op de beursverrichtingen (TOB — 0.12% / 0.35% / 1.32%):
   - Wetboek diverse rechten en taksen (WDRT), Art. 120-126/2.
   - https://financien.belgium.be/nl/particulieren/internationaal/buitenlandse-inkomsten-en-rekeningen/taks-op-beursverrichtingen
3. Reynderstaks (30% Roerende Voorheffing on Fixed-Income Funds >10% Debt Claims):
   - Wetboek van de Inkomstenbelastingen 1992 (WIB 92), Art. 19bis.
   - https://eservices.minfin.fgov.be/myminfin-web/pages/public/fisconet
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from paslood.domain.money import Money


class TobTier(StrEnum):
    """Belgian Stock Exchange Tax (Taks op de beursverrichtingen - WDRT Art. 120) tiers."""

    LOW_012 = "0.12"
    MID_035 = "0.35"
    HIGH_132 = "1.32"
    EXEMPT = "0.00"


# Statutory TOB Plafonds (Maximum tax per transaction per WDRT Art. 120)
TOB_PLAFONDS_EUR: dict[TobTier, Decimal] = {
    TobTier.LOW_012: Decimal("1300.00"),
    TobTier.MID_035: Decimal("1600.00"),
    TobTier.HIGH_132: Decimal("4000.00"),
    TobTier.EXEMPT: Decimal("0.00"),
}


class BrokerTaxProfile(StrEnum):
    """Execution and withholding tax profiles for Belgian vs. foreign custodians."""

    BELGIAN_BROKER = "BELGIAN_BROKER"  # Saxo Belgium, Bolero, KBC, Rebel, Keytrade (withholds TOB)
    EQUATEPLUS_CH = "EQUATEPLUS_CH"  # Equatex AG Zurich (0.35% commission + 0.15% Swiss stamp duty; no BE TOB withheld)
    FOREIGN_DIY = "FOREIGN_DIY"  # Foreign broker without BE TOB withholding


@dataclass(frozen=True)
class BelgianTaxCitation:
    """Official statutory reference and FOD Financiën verification URL."""

    key: str
    title: str
    statutory_article: str
    summary: str
    official_url: str


BELGIAN_TAX_CITATIONS: tuple[BelgianTaxCitation, ...] = (
    BelgianTaxCitation(
        key="meerwaardebelasting_2026",
        title="Meerwaardebelasting op financiële activa (2026)",
        statutory_article="Art. 90, eerste lid, 9° & Art. 101-102 WIB 92",
        summary=(
            "10% tax on net realized capital gains above the €10,000 annual exemption "
            "(+€1,000/yr carryover up to €15,000; doubled for joint filing). For assets "
            "acquired on or before 31 Dec 2025, cost basis is max(closing price on 31 Dec 2025, "
            "historical purchase price)."
        ),
        official_url="https://financien.belgium.be/nl/particulieren/belastingen/inkomstenbelastingen/meerwaardebelasting",
    ),
    BelgianTaxCitation(
        key="tob_wdrt",
        title="Taks op de beursverrichtingen (TOB)",
        statutory_article="Art. 120-126/2 WDRT (Wetboek diverse rechten en taksen)",
        summary=(
            "0.12% (cap €1,300), 0.35% (cap €1,600 for individual equities), or 1.32% (cap €4,000). "
            "For foreign custodians not withholding Belgian TOB (e.g. Equatex AG Zurich), the investor "
            "must file and pay TOB by the last working day of the second month following the trade."
        ),
        official_url="https://financien.belgium.be/nl/particulieren/internationaal/buitenlandse-inkomsten-en-rekeningen/taks-op-beursverrichtingen",
    ),
    BelgianTaxCitation(
        key="reynders_art19bis",
        title="Reynderstaks (Meerwaarden op obligatie- en gemengde fondsen)",
        statutory_article="Art. 19bis WIB 92 (Fisconetplus)",
        summary=(
            "30% roerende voorheffing on the fixed-income/cash component of capital gains for funds "
            "investing >10% in debt claims (schuldvorderingen). No €10,000 exemption applies to the "
            "Art. 19bis bond portion; the remaining equity portion falls under the 10% CGT."
        ),
        official_url="https://eservices.minfin.fgov.be/myminfin-web/pages/public/fisconet",
    ),
)


def calculate_tob_tax(gross_amount: Money, tier: TobTier | str = TobTier.MID_035) -> Money:
    """Calculates Belgian Stock Exchange Tax (TOB) applying statutory WDRT Art. 120 caps."""
    try:
        resolved_tier = TobTier(str(tier))
    except ValueError:
        resolved_tier = TobTier.MID_035

    rate_pct = Decimal(resolved_tier.value)
    if rate_pct <= Decimal("0.00") or gross_amount.amount <= Decimal("0.00"):
        return Money(Decimal("0.00"), gross_amount.currency)

    raw_tob = (gross_amount.amount * (rate_pct / Decimal("100.0"))).quantize(Decimal("0.01"))
    cap = TOB_PLAFONDS_EUR.get(resolved_tier, Decimal("1600.00"))
    capped_tob = min(raw_tob, cap)
    return Money(capped_tob, gross_amount.currency)
