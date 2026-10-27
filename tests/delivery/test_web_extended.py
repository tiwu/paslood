"""Extended web API and Repository delivery tests."""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.delivery.web.app import create_app
from paslood.domain.asset import Asset
from paslood.domain.money import Money


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_health_check(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
@respx.mock
async def test_mcp_server_test_ping(test_app):
    respx.post("http://localhost:4000/mcp").respond(200, json={"jsonrpc": "2.0", "result": {}})
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "http://localhost:4000/mcp"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "latency_ms" in data

        # Failing ping
        respx.post("http://unreachable-host/mcp").mock(side_effect=Exception("Connection refused"))
        resp_err = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "http://unreachable-host/mcp"},
        )
        assert resp_err.status_code == 200
        assert resp_err.json()["status"] == "error"


@pytest.mark.asyncio
async def test_ingest_generic_csv_endpoint(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        csv_content = (
            "name,symbol,asset_class,shares,current_value,currency\n"
            "Vanguard FTSE All-World,VWCE,ETF,20,2400.00,EUR\n"
        )
        files = {"file": ("generic.csv", csv_content.encode("utf-8"), "text/csv")}
        resp = await client.post("/api/ingest/generic", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_count"] == 1
        assert data["total_value"] == 2400.0


@pytest.mark.asyncio
async def test_pdt_oauth_connect_and_callback(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Connect initiates OAuth and returns auth_url
        with patch(
            "paslood.adapters.ingestion.pdt_auth.PdtAuthManager.register_client",
            new_callable=AsyncMock,
            return_value="client-xyz",
        ):
            conn_resp = await client.get("/api/auth/pdt/connect")
            assert conn_resp.status_code == 200
            data = conn_resp.json()
            assert "auth_url" in data
            assert "state" in data

            # Callback with invalid state
            cb_bad = await client.get("/api/auth/pdt/callback?code=abc&state=wrong-state")
            assert cb_bad.status_code == 307
            assert "pdt_error=" in cb_bad.headers["location"]


@pytest.mark.asyncio
async def test_pdt_sync_endpoint(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Disconnect explicitly first to ensure no token
        await client.post("/api/auth/pdt/disconnect")
        resp_no_token = await client.post("/api/mcp/pdt/sync")
        assert resp_no_token.status_code == 400

        # Save manual token
        await client.post(
            "/api/auth/pdt/manual",
            json={"auth_token": "valid-token", "mcp_url": "http://localhost:3000/mcp"},
        )

        # Mock sync holdings
        with patch(
            "paslood.adapters.ingestion.pdt_mcp.PdtMcpGateway.fetch_portfolio_assets",
            new_callable=AsyncMock,
            return_value=[Asset(id="1", name="Apple", current_value=Money.from_val(5000.0))],
        ):
            resp_sync = await client.post("/api/mcp/pdt/sync")
            assert resp_sync.status_code == 200
            assert resp_sync.json()["asset_count"] == 1


def test_config_repository_crud(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "crud_test.yaml")

    # Add custom MCP server
    srv = {"id": "srv1", "name": "Custom Node", "url": "http://localhost:9000/mcp"}
    repo.add_mcp_server(srv)
    servers = repo.load_settings()["mcp_servers"]
    assert any(s.get("id") == "srv1" for s in servers)

    # Delete custom MCP server
    repo.delete_mcp_server("srv1")
    servers2 = repo.load_settings()["mcp_servers"]
    assert not any(s.get("id") == "srv1" for s in servers2)

    # Save transaction classification rule
    repo.save_transaction_rule({"pattern": "ALDI", "category": "GROCERIES"})
    rules = repo.load_transaction_rules()
    assert any(r.get("pattern") == "ALDI" for r in rules)

    # Update PDT sync timestamp
    repo.update_pdt_sync_timestamp()
    settings = repo.load_settings()
    assert settings["pdt"]["last_sync"] is not None
