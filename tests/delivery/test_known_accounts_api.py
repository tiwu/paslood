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
