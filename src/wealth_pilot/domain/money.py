"""Money domain entity with high-precision arithmetic and formatting."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


class Money:
    """Immutable representation of a monetary value in a specific currency."""

    __slots__ = ("_amount", "_currency")

    def __init__(
        self, amount: Decimal | int | float | str = Decimal("0.00"), currency: str = "EUR"
    ) -> None:
        if isinstance(amount, Decimal):
            self._amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif isinstance(amount, (int, float)):
            self._amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif isinstance(amount, str):
            clean = (
                amount.replace("€", "")
                .replace("$", "")
                .replace(" ", "")
                .replace(".", "")
                .replace(",", ".")
            )
            try:
                self._amount = Decimal(clean).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except InvalidOperation:
                self._amount = Decimal("0.00")
        else:
            self._amount = Decimal("0.00")
        self._currency = currency.upper().strip()

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    @classmethod
    def from_val(cls, value: Any, currency: str = "EUR") -> Money:
        if isinstance(value, Money):
            return value
        if isinstance(value, dict):
            val = value.get("value", value.get("amount", 0.0))
            curr = str(value.get("currency", currency) or currency)
            return cls(val, curr)
        if isinstance(value, (int, float, str, Decimal)):
            return cls(value, currency)
        return cls(Decimal("0.00"), currency)

    def format(self, show_symbol: bool = True, decimals: int = 2) -> str:
        symbol = (
            "€"
            if self._currency == "EUR"
            else ("$" if self._currency == "USD" else f"{self._currency} ")
        )
        quant = Decimal(f"0.{'0' * decimals}") if decimals > 0 else Decimal("1")
        quantized = self._amount.quantize(quant, rounding=ROUND_HALF_UP)
        sign = "-" if quantized < 0 else ""
        abs_amt = abs(quantized)
        int_part = f"{int(abs_amt):,}".replace(",", ".")
        dec_part = str(abs_amt).split(".")[1] if "." in str(abs_amt) and decimals > 0 else ""
        num_str = f"{sign}{int_part},{dec_part}" if decimals > 0 else f"{sign}{int_part}"
        if show_symbol:
            return f"{symbol} {num_str}"
        return num_str

    def __add__(self, other: Money | Decimal | int | float) -> Money:
        val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return Money(self._amount + val, self._currency)

    def __sub__(self, other: Money | Decimal | int | float) -> Money:
        val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return Money(self._amount - val, self._currency)

    def __mul__(self, other: Decimal | int | float) -> Money:
        multiplier = other if isinstance(other, Decimal) else Decimal(str(other))
        return Money(self._amount * multiplier, self._currency)

    def __truediv__(self, other: Decimal | int | float) -> Money:
        divisor = other if isinstance(other, Decimal) else Decimal(str(other))
        if divisor == 0:
            return Money(Decimal("0.00"), self._currency)
        return Money(self._amount / divisor, self._currency)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self._amount == other.amount and self._currency == other.currency
        return False

    def __lt__(self, other: Money) -> bool:
        return self._amount < other.amount

    def __le__(self, other: Money) -> bool:
        return self._amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        return self._amount > other.amount

    def __ge__(self, other: Money) -> bool:
        return self._amount >= other.amount

    def __repr__(self) -> str:
        return f"Money({self._amount}, '{self._currency}')"
