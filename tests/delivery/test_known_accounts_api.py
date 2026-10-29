"""Delivery API tests for Known Accounts endpoints (#43)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.delivery.web.app import create_app


@pytest.mark.asyncio
async def test_known_accounts_api_lifecycle(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    repo = ConfigRepository(config_path=config_file)
    app = create_app(config_repo=repo)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initial list empty
        res = await client.get("/api/accounts/known")
        assert res.status_code == 200
        assert res.json()["accounts"] == []

        # Add Saxo account
        res_post = await client.post(
            "/api/accounts/known",
            json={
                "account_number": "BE99 1234 5678 9012",
                "label": "Saxo Investor",
                "account_type": "INVESTMENT",
                "institution": "Saxo",
            },
        )
        assert res_post.status_code == 200
        created = res_post.json()["account"]
        assert created["label"] == "Saxo Investor"
        acc_id = created["id"]

        # List shows account
        res_list = await client.get("/api/accounts/known")
        assert res_list.status_code == 200
        assert len(res_list.json()["accounts"]) == 1

        # Delete account
        res_del = await client.delete(f"/api/accounts/known/{acc_id}")
        assert res_del.status_code == 200

        # List is empty again
        res_final = await client.get("/api/accounts/known")
        assert res_final.json()["accounts"] == []


@pytest.mark.asyncio
async def test_known_account_edit_and_retroactive_transaction_reclassification(
    tmp_path: Path,
) -> None:
    """Editing or creating a known account with spaces in IBAN updates the account and reclassifies existing transactions."""
    from decimal import Decimal

    from paslood.adapters.repositories.local_db import LocalDbRepository
    from paslood.domain.balance_sheet import Money, Transaction

    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)

    # Pre-existing transactions before known account was registered
    tx1 = Transaction(
        id="tx-saxo-1",
        date="2026-06-01",
        amount=Money(Decimal("-1000.00")),
        account_id="BE90 7350 1719 2832",
        description="Maandelijkse belegging",
        counterparty_name="TIM WUYTS",
        counterparty_iban="BE99123456789012",
        category="LIVING_EXPENSES",
    )
    tx2 = Transaction(
        id="tx-bunq-sav-1",
        date="2026-06-05",
        amount=Money(Decimal("-500.00")),
        account_id="NL31 BUNQ 2093 8099 82",
        description="Transfer to NL28 BUNQ 2120 8248 27",
        counterparty_name="WUYTS TIM",
        counterparty_iban="NL28BUNQ2120824827",
        category="LIVING_EXPENSES",
    )
    db.save_transactions([tx1, tx2], source="kbc_csv")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create known account with spaces in IBAN
        res_create = await client.post(
            "/api/accounts/known",
            json={
                "account_number": "BE99 1234 5678 9012",
                "label": "Saxo Account",
                "account_type": "CHECKING",
                "institution": "Saxo",
            },
        )
        assert res_create.status_code == 200
        acc_id = res_create.json()["account"]["id"]

        # Transaction 1 should now be reclassified to TRANSFER (since type was CHECKING)
        txs_after_create = {t.id: t for t in db.get_transactions()}
        assert txs_after_create["tx-saxo-1"].category == "TRANSFER"

        # 2. Edit the known account (change label and account_type from CHECKING to INVESTMENT)
        res_edit = await client.put(
            f"/api/accounts/known/{acc_id}",
            json={
                "account_number": "BE99 1234 5678 9012",
                "label": "Saxo Investor VIP",
                "account_type": "INVESTMENT",
                "institution": "Saxo Bank",
            },
        )
        assert res_edit.status_code == 200
        edited = res_edit.json()["account"]
        assert edited["id"] == acc_id
        assert edited["label"] == "Saxo Investor VIP"
        assert edited["account_type"] == "INVESTMENT"

        # Verify only 1 account exists and tx-saxo-1 was retroactively updated to INVESTMENTS!
        res_list = await client.get("/api/accounts/known")
        assert len(res_list.json()["accounts"]) == 1
        assert res_list.json()["accounts"][0]["label"] == "Saxo Investor VIP"

        txs_after_edit = {t.id: t for t in db.get_transactions()}
        assert txs_after_edit["tx-saxo-1"].category == "INVESTMENTS"

        # 3. Also test discovered accounts endpoint recognizes known account despite spaces
        res_disc = await client.get("/api/accounts/discovered")
        assert res_disc.status_code == 200
