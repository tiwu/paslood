"""Generic CSV & Excel Ingestion Gateway."""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from paslood.adapters.ingestion.base import BaseIngestionGateway
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.money import Money

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
        "Microsoft Corporation",
        "MSFT",
        "US5949181045",
        "EQUITY",
        "30.0",
        "420.00",
        "12600.00",
        "Broker",
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

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="iso-8859-1", errors="replace")

        # Normalize line endings
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line for line in normalized.splitlines() if line.strip()]
        if not lines:
            return []

        # Check for KBC Positie-overzicht
        if any(
            "positie-overzicht" in line.lower() or "kbc easy invest" in line.lower()
            for line in lines[:10]
        ):
            return self._parse_kbc_position_overview(lines)

        # Standard generic CSV parsing
        return self._parse_standard_generic(lines)

    def _parse_kbc_position_overview(self, lines: list[str]) -> list[Asset]:
        """Parses KBC Positie-overzicht exports with sep=; preamble and Belgian numbers."""
        # Find header index (contains Productklasse and Waardeinfo)
        header_idx = -1
        for idx, line in enumerate(lines):
            low = line.lower()
            if "productklasse" in low and ("waardeinfo" in low or "isin" in low):
                header_idx = idx
                break

        if header_idx == -1:
            return []

        reader = csv.DictReader(lines[header_idx:], delimiter=";")
        assets: list[Asset] = []

        for i, row in enumerate(reader):
            prod_class = str(row.get("Productklasse", "")).strip().lower()
            isin_or_acc = str(row.get("Waardeinfo/ISIN", "")).strip()
            name = str(row.get("Naam product", "")).strip()
            val_raw = str(row.get("Huidige waarde in EUR", "")).strip()

            if not val_raw and not name and not isin_or_acc:
                continue

            # Parse Belgian currency amount: 12.038,76 -> 12038.76
            clean_val = val_raw.replace(".", "").replace(",", ".")
            try:
                current_val = Decimal(clean_val)
            except Exception:
                current_val = Decimal("0.00")

            shares_raw = str(row.get("Aantal", "")).strip().replace(".", "").replace(",", ".")
            try:
                shares = Decimal(shares_raw) if shares_raw else Decimal("1.0")
            except Exception:
                shares = Decimal("1.0")

            if (
                "spaarrekening" in prod_class
                or "zichtrekening" in prod_class
                or "cash" in prod_class
            ):
                # Extract clean IBAN e.g. BE63 7450 2071 3108 EUR -> BE63745020713108
                iban_clean = re.sub(r"[^A-Z0-9]", "", isin_or_acc.replace("EUR", "").strip())
                acc_name = (
                    f"KBC Spaarrekening ({iban_clean})"
                    if iban_clean
                    else (name or "KBC Spaarrekening")
                )
                asset_id = f"kbc-checking-{iban_clean}" if iban_clean else f"kbc-savings-{i}"

                assets.append(
                    Asset(
                        id=asset_id,
                        name=acc_name,
                        symbol="CASH",
                        isin=None,
                        asset_class=AssetClass.CASH,
                        current_value=Money(current_val, "EUR"),
                        quantity=Decimal("1.0"),
                        institution="KBC",
                        account_id=iban_clean,
                        currency="EUR",
                    )
                )
            else:
                # Beleggingsfondsen / Pension funds / Equity
                isin = isin_or_acc if len(isin_or_acc) == 12 else None
                asset_name = name or (
                    f"KBC Beleggingsfonds ({isin})" if isin else f"KBC Asset {i + 1}"
                )
                if "pension" in asset_name.lower() or "pensioen" in asset_name.lower():
                    asset_class = AssetClass.FIXED_INCOME
                else:
                    asset_class = AssetClass.EQUITY

                assets.append(
                    Asset(
                        id=f"kbc-pos-{isin or i}",
                        name=asset_name,
                        symbol=isin or "",
                        isin=isin,
                        asset_class=asset_class,
                        current_value=Money(current_val, "EUR"),
                        quantity=shares,
                        institution="KBC",
                        currency="EUR",
                    )
                )

        return assets

    def _parse_standard_generic(self, lines: list[str]) -> list[Asset]:
        delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
        reader = csv.DictReader(lines, delimiter=delimiter)
        assets: list[Asset] = []

        for i, row in enumerate(reader):
            # Guard against invalid rows where keys don't look like an asset table
            name = row.get("name") or row.get("Name") or row.get("security")
            symbol = row.get("symbol") or row.get("Symbol") or row.get("ticker") or ""
            isin = row.get("isin") or row.get("ISIN") or None
            current_value_raw = (
                row.get("current_value") or row.get("total_value") or row.get("value")
            )

            if not name and not symbol and not isin and not current_value_raw:
                continue

            asset_name = name or f"Asset-{i + 1}"
            institution = (
                row.get("institution") or row.get("broker") or row.get("bank") or "Manual Import"
            )
            currency = row.get("currency") or row.get("Currency") or "EUR"

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
                elif "PENSION" in raw_class or "FIXED_INCOME" in raw_class or "BOND" in raw_class:
                    asset_class = AssetClass.FIXED_INCOME
                else:
                    asset_class = AssetClass.EQUITY

            shares_str = str(
                row.get("shares") or row.get("quantity") or row.get("amount") or "1.0"
            ).replace(",", ".")
            try:
                shares = Decimal(shares_str)
            except Exception:
                shares = Decimal("1.0")

            val_str = str(current_value_raw or "0.0").replace(",", ".")
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
                    id=f"gen-{i}-{symbol or asset_name}",
                    name=asset_name,
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
