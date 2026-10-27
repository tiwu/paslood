"""KBC Bank CSV Export Gateway (Belgian format parser)."""

from __future__ import annotations

import csv
import hashlib
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from paslood.adapters.ingestion.base import BaseIngestionGateway
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import MonthlyCashflow, Transaction
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase


class KbcCsvGateway(BaseIngestionGateway):
    """Parses Belgian KBC Bank statement exports (semicolon-delimited, ISO-8859-1)."""

    def __init__(self, categorizer: CategorizeTransactionsUseCase | None = None) -> None:
        self.categorizer = categorizer or CategorizeTransactionsUseCase()

    def parse_file(self, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"KBC CSV file not found: {file_path}")

        # Read file with ISO-8859-1 encoding fallback
        try:
            content = path.read_text(encoding="iso-8859-1")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")

        reader = csv.DictReader(content.splitlines(), delimiter=";")
        rows = list(reader)

        if not rows:
            return {
                "account_number": "",
                "account_holder": "",
                "latest_balance": Money(Decimal("0.00")),
                "cash_asset": Asset(
                    id="kbc-cash", name="KBC Checking", asset_class=AssetClass.CASH
                ),
                "transactions": [],
                "discovered_liabilities": [],
                "cashflow": MonthlyCashflow(),
            }

        first_row = rows[0]
        account_number = str(first_row.get("Rekeningnummer", "")).strip()
        account_holder = str(first_row.get("Naam", "")).strip()
        currency = str(first_row.get("Munt", "EUR")).strip() or "EUR"

        latest_saldo_str = str(first_row.get("Saldo", "0")).strip()
        latest_balance = self._parse_euro_amount(latest_saldo_str, currency)

        # Parse transactions
        raw_txs: list[Transaction] = []
        mortgage_payments: dict[str, Decimal] = {}
        consumer_debt_payments: dict[str, Decimal] = {}

        for row in rows:
            date_raw = str(row.get("Datum", "")).strip()
            formatted_date = self._format_date(date_raw)

            amount_str = str(row.get("Bedrag", "0")).strip()
            amount = self._parse_euro_amount(amount_str, currency)

            saldo_row_str = str(row.get("Saldo", "")).strip()
            balance_after = (
                self._parse_euro_amount(saldo_row_str, currency) if saldo_row_str else None
            )

            desc = str(row.get("Omschrijving", "")).strip()
            vrije_med = str(row.get("Vrije mededeling", "")).strip()
            full_desc = f"{desc} {vrije_med}".strip()

            counterparty_name = str(row.get("Naam tegenpartij", "")).strip()
            counterparty_iban = str(row.get("rekeningnummer tegenpartij", "")).strip()

            # Scan for loan / mortgage references in description
            if "WONINGKREDIET" in full_desc.upper():
                ref_match = re.search(r"420-\d{7}-\d{2}", full_desc)
                ref_key = (
                    ref_match.group(0)
                    if ref_match
                    else f"woningkrediet-{len(mortgage_payments) + 1}"
                )
                mortgage_payments[ref_key] = abs(amount.amount)
            elif "FLEX BUDGET" in full_desc.upper() or "KREDIET" in full_desc.upper():
                ref_match = re.search(r"420-\d{7}-\d{2}", full_desc)
                ref_key = (
                    ref_match.group(0)
                    if ref_match
                    else f"flex-budget-{len(consumer_debt_payments) + 1}"
                )
                consumer_debt_payments[ref_key] = abs(amount.amount)

            afschrift = str(row.get("Afschriftnummer", "")).strip()
            hash_input = (
                f"{account_number}|{formatted_date}|{amount.amount}|{full_desc}|{afschrift}"
            )
            tx_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

            tx = Transaction(
                id=f"kbc-{account_number}-{tx_hash}",
                date=formatted_date,
                amount=amount,
                account_id=account_number,
                description=full_desc,
                counterparty_name=counterparty_name,
                counterparty_iban=counterparty_iban,
                balance_after=balance_after,
                raw_data=dict(row),
            )
            raw_txs.append(tx)

        # Categorize transactions
        transactions = self.categorizer.execute(raw_txs)

        # Discovered liabilities - bank statement contains monthly payment only (balance and APR require user input)
        discovered_liabilities: list[Liability] = []
        for ref, monthly_amt in mortgage_payments.items():
            discovered_liabilities.append(
                Liability(
                    id=f"mortgage-{ref}",
                    name=f"Woningkrediet ({ref})",
                    loan_type=LoanType.MORTGAGE,
                    principal_balance=Money(Decimal("0.00"), currency),
                    interest_rate_pct=Decimal("0.00"),
                    monthly_payment=Money(monthly_amt, currency),
                    institution="KBC",
                    account_reference=ref,
                )
            )

        for ref, monthly_amt in consumer_debt_payments.items():
            discovered_liabilities.append(
                Liability(
                    id=f"flex-{ref}",
                    name=f"Flex Budget ({ref})",
                    loan_type=LoanType.CONSUMER_LOAN,
                    principal_balance=Money(Decimal("0.00"), currency),
                    interest_rate_pct=Decimal("0.00"),
                    monthly_payment=Money(monthly_amt, currency),
                    institution="KBC",
                    account_reference=ref,
                )
            )

        # Compute Cashflow Metrics
        inflows = [t.amount.amount for t in transactions if t.is_inflow]
        total_income = sum(inflows, Decimal("0.00"))
        # Average per month based on months that had inflows
        distinct_income_months = (
            len(
                {
                    t.date[:7]
                    for t in transactions
                    if t.is_inflow and t.amount.amount > Decimal("100.0")
                }
            )
            or 1
        )
        avg_monthly_income = (total_income / Decimal(str(distinct_income_months))).quantize(
            Decimal("0.01")
        )

        mortgage_total_monthly = sum(mortgage_payments.values(), Decimal("0.00"))
        consumer_total_monthly = sum(consumer_debt_payments.values(), Decimal("0.00"))
        total_monthly_debt = mortgage_total_monthly + consumer_total_monthly

        cashflow = MonthlyCashflow(
            monthly_income=Money(avg_monthly_income, currency),
            fixed_costs=Money(Decimal("1200.00"), currency),  # Living baseline estimate
            debt_payments=Money(total_monthly_debt, currency),
            living_expenses=Money(Decimal("800.00"), currency),
        )

        cash_asset = Asset(
            id=f"kbc-checking-{account_number}",
            name=f"KBC Checking ({account_number})",
            symbol="CASH",
            asset_class=AssetClass.CASH,
            current_value=latest_balance,
            institution="KBC",
            account_id=account_number,
            currency=currency,
        )

        return {
            "account_number": account_number,
            "account_holder": account_holder,
            "latest_balance": latest_balance,
            "cash_asset": cash_asset,
            "transactions": transactions,
            "discovered_liabilities": discovered_liabilities,
            "cashflow": cashflow,
        }

    def _parse_euro_amount(self, raw_str: str, currency: str = "EUR") -> Money:
        clean = raw_str.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return Money(Decimal(clean), currency)
        except Exception:
            return Money(Decimal("0.00"), currency)

    def _format_date(self, raw_date: str) -> str:
        # Expected DD/MM/YYYY
        parts = raw_date.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return raw_date
