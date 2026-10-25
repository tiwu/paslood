"""Security tests for SSRF prevention and arbitrary cloud-sync path restriction."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.adapters.settings import AppSettings
from wealth_pilot.delivery.web.app import create_app


@pytest.fixture
def hardened_app(tmp_path: Path):
    settings = AppSettings(
        mode="self_host",
        data_dir=tmp_path,
        auth_mode="none",
    )
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    return create_app(config_repo=repo, app_settings=settings)


@pytest.mark.asyncio
async def test_cloud_sync_restricted_in_self_host_mode(hardened_app):
    transport = ASGITransport(app=hardened_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/backup/cloud-sync",
            json={"sync_dir": "/etc", "passphrase": "some-passphrase", "action": "push"},
        )
        assert res.status_code == 403
        assert "disabled in remote/container mode" in res.json()["detail"]


@pytest.mark.asyncio
async def test_mcp_server_test_blocks_loopback_in_self_host_mode(hardened_app):
    transport = ASGITransport(app=hardened_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "http://127.0.0.1:11434"},
        )
        assert res.status_code == 403
        assert "Access to internal or private network" in res.json()["detail"]
