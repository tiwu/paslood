"""Tests for New User-Requested Features:
- PDT OAuth Auto-sync & confirmation
- AI Advisor model discovery & model selection
- Manual real estate assets & mortgage debts
- Portfolio holdings bucket assignment
- Projection timeframe & custom milestones
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app
from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.money import Money


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_manual_assets_crud(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Add Real Estate Asset
        resp = await client.post(
            "/api/assets/manual",
            json={
                "name": "Family Residence (Leuven)",
                "asset_class": "REAL_ESTATE",
                "current_value": 450000.0,
                "institution": "Private Property",
                "currency": "EUR",
            },
        )
        assert resp.status_code == 200
        asset_id = resp.json()["asset"]["id"]
        assert asset_id.startswith("asset-")

        # 2. Check overview includes this manual asset
        ov_resp = await client.get("/api/overview")
        assert ov_resp.status_code == 200
        data = ov_resp.json()
        assert any(
            a["id"] == asset_id and a["name"] == "Family Residence (Leuven)" for a in data["assets"]
        )

        # 3. Delete manual asset
        del_resp = await client.delete(f"/api/assets/manual/{asset_id}")
        assert del_resp.status_code == 200

        # Check removed
        ov_resp2 = await client.get("/api/overview")
        data2 = ov_resp2.json()
        assert not any(a["id"] == asset_id for a in data2["assets"])


@pytest.mark.asyncio
async def test_manual_liabilities_crud(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Add Mortgage Liability
        resp = await client.post(
            "/api/liabilities/manual",
            json={
                "name": "KBC Home Mortgage",
                "loan_type": "MORTGAGE",
                "principal_balance": 280000.0,
                "interest_rate_pct": 1.85,
                "monthly_payment": 1150.0,
                "institution": "KBC Bank",
            },
        )
        assert resp.status_code == 200
        liab_id = resp.json()["liability"]["id"]
        assert liab_id.startswith("debt-")

        # 2. Check overview includes this debt
        ov_resp = await client.get("/api/overview")
        assert ov_resp.status_code == 200
        data = ov_resp.json()
        assert any(
            liab["id"] == liab_id and liab["name"] == "KBC Home Mortgage"
            for liab in data["liabilities"]
        )

        # 3. Delete liability
        del_resp = await client.delete(f"/api/liabilities/manual/{liab_id}")
        assert del_resp.status_code == 200

        # Check removed
        ov_resp2 = await client.get("/api/overview")
        data2 = ov_resp2.json()
        assert not any(liab["id"] == liab_id for liab in data2["liabilities"])


@pytest.mark.asyncio
async def test_assign_asset_to_bucket(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Add a manual equity asset
        asset_resp = await client.post(
            "/api/assets/manual",
            json={
                "name": "Custom Semiconductor Stock",
                "symbol": "SEMI",
                "asset_class": "EQUITY",
                "current_value": 25000.0,
            },
        )
        assert asset_resp.status_code == 200

        # Assign SEMI to tech-growth bucket
        assign_resp = await client.post(
            "/api/buckets/assign-asset",
            json={
                "bucket_id": "tech-growth",
                "symbol": "SEMI",
            },
        )
        assert assign_resp.status_code == 200
        allocations = assign_resp.json()["allocations"]
        tech_bucket = next(b for b in allocations if b["bucket_id"] == "tech-growth")
        assert tech_bucket["current_value"] >= 25000.0

        # Verify overview asset list shows tech-growth
        ov_resp = await client.get("/api/overview")
        data = ov_resp.json()
        semi_asset = next(a for a in data["assets"] if a["symbol"] == "SEMI")
        assert semi_asset["bucket_id"] == "tech-growth"


@pytest.mark.asyncio
async def test_ai_models_and_advise(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Fetch Gemini models
        models_resp = await client.get("/api/ai/models?provider=gemini")
        assert models_resp.status_code == 200
        models = models_resp.json()["models"]
        assert len(models) >= 3
        assert any(m["id"] == "gemini-2.5-flash" for m in models)

        # 2. Fetch OpenAI models
        models_resp_oai = await client.get("/api/ai/models?provider=openai")
        assert models_resp_oai.status_code == 200
        assert any(m["id"] == "gpt-4o-mini" for m in models_resp_oai.json()["models"])

        # 3. Call advise with specific model (fallback algorithmic when no key)
        adv_resp = await client.post(
            "/api/ai/advise",
            json={
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "question": "What is my recommended rebalance strategy?",
            },
        )
        assert adv_resp.status_code == 200
        assert "advice" in adv_resp.json()


@pytest.mark.asyncio
async def test_projection_timeframe(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 10 years projection
        resp10 = await client.get("/api/projection?years=10&cagr=8.0")
        assert resp10.status_code == 200
        data10 = resp10.json()
        assert data10["years"] == 10
        assert data10["cagr"] == 8.0
        assert len(data10["trajectory"]) == 11

        # 5 years projection
        resp5 = await client.get("/api/projection?years=5&cagr=5.5")
        assert resp5.status_code == 200
        data5 = resp5.json()
        assert len(data5["trajectory"]) == 6


@pytest.mark.asyncio
async def test_milestones_crud(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get default milestones
        get_resp = await client.get("/api/milestones")
        assert get_resp.status_code == 200
        milestones = get_resp.json()["milestones"]
        assert len(milestones) >= 4

        # 2. Save custom milestones
        custom = [
            {"id": "c1", "name": "First 50k", "target_amount": 50000.0, "currency": "EUR"},
            {"id": "c2", "name": "Coast FIRE", "target_amount": 350000.0, "currency": "EUR"},
        ]
        post_resp = await client.post("/api/milestones", json={"milestones": custom})
        assert post_resp.status_code == 200

        # 3. Check overview reflects custom milestones
        ov_resp = await client.get("/api/overview")
        data = ov_resp.json()
        ms = data["milestones"]
        assert len(ms) == 2
        assert ms[0]["name"] == "First 50k"
        assert "target_formatted" in ms[0]


@pytest.mark.asyncio
async def test_pdt_oauth_auto_sync_callback(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as client:
        # Initiate connection to register state
        conn_resp = await client.get("/api/auth/pdt/connect")
        state_token = conn_resp.json()["state"]

        fake_tokens = {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "client_id": "test-client",
            "expires_at": 9999999999,
        }
        mock_asset = Asset(
            id="pdt-1",
            name="Mock ASML",
            symbol="ASML",
            asset_class=AssetClass.EQUITY,
            current_value=Money.from_val(15000.0),
        )

        with (
            patch(
                "wealth_pilot.adapters.ingestion.pdt_auth.PdtAuthManager.exchange_code",
                new_callable=AsyncMock,
            ) as mock_exchange,
            patch(
                "wealth_pilot.adapters.ingestion.pdt_mcp.PdtMcpGateway.fetch_portfolio_assets",
                new_callable=AsyncMock,
            ) as mock_fetch,
        ):
            mock_exchange.return_value = fake_tokens
            mock_fetch.return_value = [mock_asset]

            callback_resp = await client.get(
                f"/api/auth/pdt/callback?code=fake-code&state={state_token}"
            )
            assert callback_resp.status_code == 307
            redirect_url = callback_resp.headers["location"]
            assert "pdt_connected=true" in redirect_url
            assert "synced_count=1" in redirect_url
