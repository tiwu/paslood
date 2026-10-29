"""Use Case: Bank Statement Ingestion, Categorization, and Unregistered Account Discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paslood.domain.account import infer_institution_from_account
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase
from paslood.use_cases.ports import (
    PortfolioRepository,
    StatementGatewayPort,
    TransactionRepository,
)


class IngestStatementUseCase:
    """Orchestrates parsing a statement file, applying classification rules,

    persisting transactions/discovered items, and detecting unregistered accounts.
    """

    def __init__(self, categorizer: CategorizeTransactionsUseCase | None = None) -> None:
        self.categorizer = categorizer or CategorizeTransactionsUseCase()

    def execute(
        self,
        file_path: str | Path,
        gateway: StatementGatewayPort,
        repo: PortfolioRepository,
        db: TransactionRepository,
        source: str = "kbc_csv",
    ) -> dict[str, Any]:
        rules = repo.load_transaction_rules()
        known_accounts = repo.load_known_accounts()

        data = gateway.parse_file(file_path)
        cash_assets = data.get("discovered_cash_assets") or (
            [data["cash_asset"]] if data.get("cash_asset") else []
        )
        discovered_liabilities = data.get("discovered_liabilities") or []

        categorized_txs = self.categorizer.execute(
            data["transactions"], rules, known_accounts=known_accounts
        )

        inserted_txs = db.save_transactions(categorized_txs, source=source)
        if cash_assets:
            db.save_discovered_assets(cash_assets, source=source)
        if discovered_liabilities:
            db.save_discovered_liabilities(discovered_liabilities)

        total_txs = len(db.get_transactions())

        clean_known_set = {
            k.account_number.replace(" ", "").upper() for k in known_accounts if k.account_number
        }
        all_account_numbers: set[str] = set()
        if data.get("account_number"):
            all_account_numbers.add(str(data["account_number"]))
        for ca in cash_assets:
            if ca.account_id:
                all_account_numbers.add(ca.account_id)
        for tx in categorized_txs:
            if tx.account_id:
                all_account_numbers.add(tx.account_id)

        unregistered: list[dict[str, str]] = []
        for acc in sorted(all_account_numbers):
            clean_acc = acc.replace(" ", "").upper()
            if clean_acc and clean_acc not in clean_known_set:
                inst = infer_institution_from_account(acc)
                unregistered.append(
                    {
                        "account_id": acc,
                        "institution_hint": inst,
                        "suggested_label": f"{inst} {acc[-4:]}" if len(acc) >= 4 else inst,
                    }
                )

        return {
            "status": "success",
            "account_number": data["account_number"],
            "latest_balance": data["latest_balance"].format(),
            "transaction_count": len(categorized_txs),
            "transactions_processed": len(categorized_txs),
            "new_transactions": inserted_txs,
            "total_cumulative_transactions": total_txs,
            "discovered_liabilities_count": len(discovered_liabilities),
            "unregistered_accounts": unregistered,
        }
