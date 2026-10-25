"""Asset and Holding domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from wealth_pilot.domain.money import Money


class AssetClass(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"
    REAL_ESTATE = "REAL_ESTATE"
    FIXED_INCOME = "FIXED_INCOME"
    CASH = "CASH"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Asset:
    """An asset holding owned across any brokerage, bank, or private custody."""

    id: str
    name: str
    symbol: str = ""
    isin: str | None = None
    asset_class: AssetClass = AssetClass.EQUITY
    current_value: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    quantity: Decimal = Decimal("1.0")
    cost_basis: Money | None = None
    institution: str = "Unknown"  # e.g., "Saxo Bank", "KBC", "DEGIRO", "EquatePlus"
    account_id: str = ""
    currency: str = "EUR"

    @property
    def unit_price(self) -> Money:
        if self.quantity <= Decimal("0"):
            return self.current_value
        return self.current_value / self.quantity

    @property
    def unrealized_gain(self) -> Money:
        if self.cost_basis is None:
            return Money(Decimal("0.00"), self.currency)
        return self.current_value - self.cost_basis

    @property
    def unrealized_gain_pct(self) -> Decimal:
        if not self.cost_basis or self.cost_basis.amount <= Decimal("0"):
            return Decimal("0.00")
        return ((self.unrealized_gain.amount / self.cost_basis.amount) * Decimal("100")).quantize(
            Decimal("0.01")
        )
