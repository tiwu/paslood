"""Generic CSV & Excel Ingestion Gateway."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Any

from wealth_pilot.adapters.ingestion.base import BaseIngestionGateway
from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.money import Money

TEMPLATE_CSV_HEADERS = [
    "name",
    "symbol",
    "isin",
    "asset_class",
    "shares",
    "current_price",
    "current_value",
    "institution",
    "currency",
]

SAMPLE_TEMPLATE_ROWS = [
    [
        "ASML Holding N.V.",
        "ASML",
        "NL0010273215",
        "EQUITY",
        "25.0",
        "1597.00",
        "39925.00",
        "Saxo Bank",
        "EUR",
    ],
    [
        "Vanguard FTSE All-World UCITS ETF",
        "VWCE",
        "IE00BK5BQT80",
        "ETF",
        "350.0",
        "132.50",
        "46375.00",
        "DEGIRO",
        "EUR",
    ],
    [
        "Amundi Physical Gold ETC",
        "GOLD",
        "FR0013416716",
        "COMMODITY",
        "120.0",
        "92.00",
        "11040.00",
        "Bolero",
        "EUR",
    ],
    [
        "Bunq High-Yield Savings",
        "SAVINGS",
        "",
        "CASH",
        "1.0",
        "15000.00",
        "15000.00",
        "Bunq",
        "EUR",
    ],
]


class GenericCsvGateway(BaseIngestionGateway):
    """Universal tabular parser for importing portfolio assets and bank balances."""

    def parse_file(self, file_path: str | Path) -> dict[str, Any]:
        assets = self.parse_assets_file(file_path)
        total_val = sum((a.current_value.amount for a in assets), Decimal("0.00"))
        return {
            "assets": assets,
            "total_value": Money(total_val),
            "asset_count": len(assets),
        }

    def parse_assets_file(self, file_path: str | Path) -> list[Asset]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect delimiter (comma or semicolon)
        sample = path.read_text(encoding="utf-8", errors="replace")[:2048]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

        assets: list[Asset] = []
        with open(path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for i, row in enumerate(reader):
                name = row.get("name") or row.get("Name") or row.get("security") or f"Asset-{i + 1}"
                symbol = row.get("symbol") or row.get("Symbol") or row.get("ticker") or ""
                isin = row.get("isin") or row.get("ISIN") or None
                institution = (
                    row.get("institution")
                    or row.get("broker")
                    or row.get("bank")
                    or "Manual Import"
                )
                currency = row.get("currency") or row.get("Currency") or "EUR"

                # Parse asset class
                raw_class = str(row.get("asset_class") or row.get("type") or "EQUITY").upper()
                try:
                    asset_class = AssetClass(raw_class)
                except ValueError:
                    if "ETF" in raw_class or "INDEX" in raw_class:
                        asset_class = AssetClass.ETF
                    elif "GOLD" in raw_class or "COMMODITY" in raw_class:
                        asset_class = AssetClass.COMMODITY
                    elif "CASH" in raw_class or "SAVINGS" in raw_class:
                        asset_class = AssetClass.CASH
                    else:
                        asset_class = AssetClass.EQUITY

                shares_str = str(
                    row.get("shares") or row.get("quantity") or row.get("amount") or "1.0"
                ).replace(",", ".")
                try:
                    shares = Decimal(shares_str)
                except Exception:
                    shares = Decimal("1.0")

                val_str = str(
                    row.get("current_value") or row.get("total_value") or row.get("value") or "0.0"
                ).replace(",", ".")
                try:
                    current_value = Money(Decimal(val_str), currency)
                except Exception:
                    current_value = Money(Decimal("0.00"), currency)

                if current_value.amount == Decimal("0.00"):
                    price_str = str(row.get("current_price") or row.get("price") or "0.0").replace(
                        ",", "."
                    )
                    try:
                        price = Decimal(price_str)
                        current_value = Money((shares * price).quantize(Decimal("0.01")), currency)
                    except Exception:
                        pass

                assets.append(
                    Asset(
                        id=f"gen-{i}-{symbol or name}",
                        name=name,
                        symbol=symbol,
                        isin=isin,
                        asset_class=asset_class,
                        current_value=current_value,
                        quantity=shares,
                        institution=institution,
                        currency=currency,
                    )
                )

        return assets

    @classmethod
    def generate_template_csv(cls) -> str:
        """Returns sample CSV content for user template export."""
        lines = [",".join(TEMPLATE_CSV_HEADERS)]
        for r in SAMPLE_TEMPLATE_ROWS:
            lines.append(",".join(f'"{c}"' if " " in c else c for c in r))
        return "\n".join(lines) + "\n"
