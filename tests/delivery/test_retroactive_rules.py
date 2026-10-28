"""Delivery and unit tests for retroactive categorization and upload feedback (#38)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app
from paslood.domain.balance_sheet import Money, Transaction


def test_local_db_apply_rule_to_transactions(tmp_path: Path) -> None:
    db = LocalDbRepository(db_path=tmp_path / "test.db")
    tx1 = Transaction(
        id="tx-1",
        date="2026-01-10",
        amount=Money(Decimal("-5.99")),
        account_id="BE90735017192832",
        description="GOOGLE*GOOGLE PLAY APP DUBLIN",
        counterparty_name="GOOGLE*GOOGLE PLAY APP",
        category="OTHER",
    )
    tx2 = Transaction(
        id="tx-2",
        date="2026-02-10",
        amount=Money(Decimal("-10.99")),
        account_id="BE90735017192832",
        description="GOOGLE*GOOGLE PLAY APP DUBLIN",
        counterparty_name="",
        category="OTHER",
    )
    tx3 = Transaction(
        id="tx-3",
        date="2026-03-10",
        amount=Money(Decimal("-50.00")),
        account_id="BE90735017192832",
        description="DELHAIZE",
        counterparty_name="DELHAIZE",
        category="GROCERIES",
    )

    db.save_transactions([tx1, tx2, tx3], source="kbc_csv")

    # Apply retroactive rule on "GOOGLE*GOOGLE PLAY"
    updated_count = db.apply_rule_to_transactions("GOOGLE*GOOGLE PLAY", "SUBSCRIPTION")
    assert updated_count == 2

    txs = {t.id: t for t in db.get_transactions()}
    assert txs["tx-1"].category == "SUBSCRIPTION"
    assert txs["tx-2"].category == "SUBSCRIPTION"
    assert txs["tx-3"].category == "GROCERIES"


@pytest.mark.asyncio
async def test_rebucket_endpoint_retroactive_application(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)

    tx1 = Transaction(
        id="tx-cc-1",
        date="2026-04-10",
        amount=Money(Decimal("-12.50")),
        account_id="CC-9128",
        description="NYX*VendingWork Station",
        counterparty_name="NYX*VendingWork",
        category="OTHER",
    )
    tx2 = Transaction(
        id="tx-cc-2",
        date="2026-05-10",
        amount=Money(Decimal("-12.50")),
        account_id="CC-9128",
        description="NYX*VendingWork Station",
        counterparty_name="NYX*VendingWork",
        category="OTHER",
    )
    db.save_transactions([tx1, tx2], source="kbc_cc")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/transactions/rebucket",
            json={
                "transaction_id": "tx-cc-1",
                "target_category": "LIVING_EXPENSES",
                "counterparty_name": "NYX*VendingWork",
                "pattern": "NYX*VendingWork",
                "remember_rule": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["updated_historical_count"] == 2

    txs = {t.id: t for t in db.get_transactions()}
    assert txs["tx-1" if "tx-1" in txs else "tx-cc-1"].category == "LIVING_EXPENSES"
    assert txs["tx-2" if "tx-2" in txs else "tx-cc-2"].category == "LIVING_EXPENSES"
