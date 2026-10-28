"""Unit tests for discovering statement accounts and summarizing unmapped accounts."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import Transaction
from paslood.domain.money import Money


def test_get_discovered_account_summaries(tmp_path: Path):
    db = LocalDbRepository(db_path=tmp_path / "test.db")

    # Ingest some transactions across accounts
    txs = [
        Transaction(
            id="tx-1",
            date="2026-10-25",
            amount=Money(Decimal("-12.50"), "EUR"),
            account_id="BE99 1234 5678 9012",
            description="Supermarket",
        ),
        Transaction(
            id="tx-2",
            date="2026-10-26",
            amount=Money(Decimal("100.00"), "EUR"),
            account_id="BE99 1234 5678 9012",
            description="Salary",
        ),
        Transaction(
            id="tx-3",
            date="2026-10-27",
            amount=Money(Decimal("50.00"), "EUR"),
            account_id="NL31BUNQ2093809982",
            description="Bunq Topup",
        ),
    ]
    db.save_transactions(txs)

    # Ingest a cash asset for bunq savings
    assets = [
        Asset(
            id="bunq-savings-NL28BUNQ2120824827",
            name="bunq (NL28BUNQ2120824827)",
            symbol="CASH",
            asset_class=AssetClass.CASH,
            current_value=Money(Decimal("3444.22"), "EUR"),
            institution="bunq",
            account_id="NL28BUNQ2120824827",
            currency="EUR",
        )
    ]
    db.save_discovered_assets(assets, source="bunq_csv")

    summaries = db.get_discovered_account_summaries()

    acc_ids = {s["account_id"] for s in summaries}
    assert "BE99 1234 5678 9012" in acc_ids
    assert "NL31BUNQ2093809982" in acc_ids
    assert "NL28BUNQ2120824827" in acc_ids

    bunq_summary = next(s for s in summaries if s["account_id"] == "NL31BUNQ2093809982")
    assert bunq_summary["institution_hint"].lower() == "bunq"
    assert bunq_summary["transaction_count"] == 1
