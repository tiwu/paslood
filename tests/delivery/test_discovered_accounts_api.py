"""Delivery tests for GET /api/accounts/discovered and upload unmapped account detection (#45)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app


@pytest.mark.asyncio
async def test_discovered_accounts_api(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)
    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ingest a bunq statement
        csv_content = (
            '"Date","Amount","Account","Counterparty","Description"\n'
            '"2026-10-25","-15.20","NL31BUNQ2093809982","Store","Groceries"\n'
        )
        res_upload = await client.post(
            "/api/ingest/bunq",
            files={"file": ("bunq_statement.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert res_upload.status_code == 200
        data = res_upload.json()
        assert len(data["unregistered_accounts"]) == 1
        assert data["unregistered_accounts"][0]["account_id"] == "NL31BUNQ2093809982"

        # Check GET /api/accounts/discovered
        res_disc = await client.get("/api/accounts/discovered")
        assert res_disc.status_code == 200
        disc_list = res_disc.json()["discovered_accounts"]
        assert len(disc_list) >= 1
        bunq_item = next(d for d in disc_list if d["account_id"] == "NL31BUNQ2093809982")
        assert bunq_item["is_known"] is False
        assert bunq_item["institution_hint"].lower() == "bunq"

        # Register the account as known
        res_post = await client.post(
            "/api/accounts/known",
            json={
                "account_number": "NL31BUNQ2093809982",
                "label": "Bunq Daily",
                "account_type": "CHECKING",
                "institution": "bunq",
            },
        )
        assert res_post.status_code == 200

        # Discovered list now marks it as known
        res_disc2 = await client.get("/api/accounts/discovered")
        disc_list2 = res_disc2.json()["discovered_accounts"]
        bunq_item2 = next(d for d in disc_list2 if d["account_id"] == "NL31BUNQ2093809982")
        assert bunq_item2["is_known"] is True
        assert bunq_item2["known_label"] == "Bunq Daily"
