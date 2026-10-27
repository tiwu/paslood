"""Delivery tests for bucket target weight API validation."""

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.delivery.web.app import create_app


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_update_single_bucket_target_validation(test_app):
    """Test that /api/buckets/target enforces 100% total weight across active buckets."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initial default sum is 50 + 35 + 5 + 10 = 100%
        # Updating core-etf to 55% causes total to be 105% -> expect 400
        res_fail = await client.post(
            "/api/buckets/target",
            json={"bucket_id": "core-etf", "name": "Core World ETFs", "target_weight_pct": 55.0},
        )
        assert res_fail.status_code == 400
        assert "must sum to 100%" in res_fail.json()["detail"]

        # Updating core-etf to 50% maintains 100% total -> expect 200
        res_ok = await client.post(
            "/api/buckets/target",
            json={"bucket_id": "core-etf", "name": "Core World ETFs", "target_weight_pct": 50.0},
        )
        assert res_ok.status_code == 200
        assert res_ok.json() == {"status": "success"}


@pytest.mark.asyncio
async def test_batch_update_bucket_targets(test_app):
    """Test that /api/buckets/targets allows atomic reallocation summing to 100%."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unbalanced batch targets (sum = 110%) -> expect 400
        res_fail = await client.post(
            "/api/buckets/targets",
            json={
                "targets": {
                    "core-etf": 55.0,
                    "tech-growth": 40.0,
                    "commodities": 5.0,
                    "cash-buffer": 10.0,
                }
            },
        )
        assert res_fail.status_code == 400
        assert "must sum to 100%" in res_fail.json()["detail"]

        # Balanced batch targets (sum = 100%: 55 + 30 + 5 + 10) -> expect 200
        res_ok = await client.post(
            "/api/buckets/targets",
            json={
                "targets": {
                    "core-etf": 55.0,
                    "tech-growth": 30.0,
                    "commodities": 5.0,
                    "cash-buffer": 10.0,
                }
            },
        )
        assert res_ok.status_code == 200
        assert res_ok.json() == {"status": "success"}

        # Verify new weights reflected in overview
        overview_res = await client.get("/api/overview")
        assert overview_res.status_code == 200
        allocations = {
            a["bucket_id"]: a["target_weight_pct"] for a in overview_res.json()["allocations"]
        }
        assert allocations["core-etf"] == 55.0
        assert allocations["tech-growth"] == 30.0
