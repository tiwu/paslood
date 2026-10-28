"""Bunq Bank CSV Statement Ingestion Gateway."""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from paslood.adapters.ingestion.base import BaseIngestionGateway
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import MonthlyCashflow, Transaction, TransactionCategory
from paslood.domain.money import Money
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase


class BunqCsvGateway(BaseIngestionGateway):
    """Parses Bunq bank export CSV files (comma-delimited, UTF-8, European decimal amounts)."""

    def __init__(self, categorizer: CategorizeTransactionsUseCase | None = None) -> None:
        self.categorizer = categorizer or CategorizeTransactionsUseCase()

    def parse_file(self, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Bunq CSV file not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="iso-8859-1", errors="replace")

        # Normalize line breaks
        normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line for line in normalized_content.splitlines() if line.strip()]
        if not lines:
            return {
                "account_number": "",
                "account_holder": "",
                "latest_balance": Money(Decimal("0.00")),
                "cash_asset": Asset(
                    id="bunq-cash", name="bunq Account", asset_class=AssetClass.CASH
                ),
                "transactions": [],
                "discovered_liabilities": [],
                "cashflow": MonthlyCashflow(),
            }

        reader = csv.DictReader(lines, delimiter=",")
        rows = list(reader)

        transactions: list[Transaction] = []
        discovered_accounts: dict[str, str] = {}
        row_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)

        for row in rows:
            date_str = (row.get("Date") or "").strip()
            amount_raw = (row.get("Amount") or "").strip()
            account_id = (row.get("Account") or "").strip()
            counterparty = (row.get("Counterparty") or "").strip()
            name = (row.get("Name") or "").strip()
            description = (row.get("Description") or "").strip()

            if not date_str and not amount_raw:
                continue

            if account_id:
                discovered_accounts[account_id] = account_id

            clean_amount = amount_raw.replace(".", "").replace(",", ".")
            try:
                amount_dec = Decimal(clean_amount)
            except Exception:
                amount_dec = Decimal("0.00")

            counterparty_name = name or counterparty

            # Occurrence index for identical same-day merchant charges
            key = (date_str, account_id, str(amount_dec), counterparty_name)
            row_counts[key] += 1
            occurrence = row_counts[key]

            tx_hash = hashlib.sha256(
                f"bunq:{date_str}:{account_id}:{amount_dec}:{counterparty_name}:{description}:{occurrence}".encode()
            ).hexdigest()[:16]

            # Categorize
            desc_lower = description.lower()
            if "bunq payday" in desc_lower or "rente" in desc_lower or "interest" in desc_lower:
                category = TransactionCategory.INVESTMENTS.value
            else:
                category = TransactionCategory.OTHER.value

            transactions.append(
                Transaction(
                    id=f"bunq-{tx_hash}",
                    date=date_str,
                    amount=Money(amount_dec, "EUR"),
                    account_id=account_id,
                    description=description,
                    counterparty_name=counterparty_name,
                    category=category,
                    raw_data=dict(row),
                )
            )

        transactions = self.categorizer.execute(transactions)

        # Calculate statement balance per discovered account
        account_balances: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for tx in transactions:
            acc = tx.account_id or "bunq"
            account_balances[acc] += tx.amount.amount

        discovered_cash_assets: list[Asset] = []
        for acc_id, bal in account_balances.items():
            discovered_cash_assets.append(
                Asset(
                    id=f"bunq-cash-{acc_id}",
                    name=f"bunq ({acc_id})",
                    symbol="CASH",
                    asset_class=AssetClass.CASH,
                    current_value=Money(bal, "EUR"),
                    institution="bunq",
                    account_id=acc_id,
                    currency="EUR",
                )
            )

        primary_account = next(iter(discovered_accounts.keys()), "bunq")
        primary_balance = account_balances.get(primary_account, Decimal("0.00"))
        primary_asset = next(
            (a for a in discovered_cash_assets if a.account_id == primary_account),
            Asset(
                id=f"bunq-cash-{primary_account}",
                name=f"bunq ({primary_account})",
                symbol="CASH",
                asset_class=AssetClass.CASH,
                current_value=Money(primary_balance, "EUR"),
                institution="bunq",
                account_id=primary_account,
                currency="EUR",
            ),
        )

        return {
            "account_number": primary_account,
            "account_holder": "",
            "latest_balance": Money(primary_balance, "EUR"),
            "cash_asset": primary_asset,
            "discovered_cash_assets": discovered_cash_assets,
            "transactions": transactions,
            "discovered_liabilities": [],
            "cashflow": MonthlyCashflow(),
        }
