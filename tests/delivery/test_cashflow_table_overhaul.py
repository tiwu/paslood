"""Delivery test for Cashflow overview serialization and pagination (#39)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app
from paslood.domain.balance_sheet import Money, Transaction


@pytest.mark.asyncio
async def test_overview_includes_account_id_and_large_history(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)

    # Insert 150 transactions across 2 accounts
    txs = []
    for i in range(150):
        acc = "BE90735017192832" if i % 2 == 0 else "NL31BUNQ2093809982"
        txs.append(
            Transaction(
                id=f"tx-{i}",
                date="2026-05-01",
                amount=Money(Decimal("-10.00")),
                account_id=acc,
                description=f"Transaction {i}",
                counterparty_name="Merchant",
                category="GROCERIES",
            )
        )
    db.save_transactions(txs, source="test")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/overview")
        assert res.status_code == 200
        data = res.json()
        assert len(data["transactions"]) == 150
        first_tx = data["transactions"][0]
        assert "account_id" in first_tx
        assert first_tx["account_id"] in ("BE90735017192832", "NL31BUNQ2093809982")
