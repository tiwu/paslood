"""Delivery tests for smart buy-only contribution advice endpoint."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app


@pytest.fixture
def api_app(tmp_path: Path):
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_contribution_advice_endpoint(api_app):
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/advice/contribution", json={"deposit": 2000.0})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["deposit"] == 2000.0
        assert "orders" in data
        assert isinstance(data["orders"], list)
