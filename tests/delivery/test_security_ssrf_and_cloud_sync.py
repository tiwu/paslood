"""Security tests for SSRF prevention and arbitrary cloud-sync path restriction."""

import socket
from pathlib import Path

import httpcore
import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.settings import AppSettings
from paslood.delivery.web.app import _PinnedMcpNetworkBackend, create_app


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


@pytest.mark.asyncio
async def test_mcp_server_test_fails_closed_when_dns_resolution_fails(hardened_app, monkeypatch):
    def fail_resolution(*args, **kwargs):
        raise socket.gaierror("DNS lookup failed")

    monkeypatch.setattr(socket, "getaddrinfo", fail_resolution)
    transport = ASGITransport(app=hardened_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "https://mcp.example.invalid"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_pinned_mcp_backend_connects_only_to_validated_addresses():
    class RecordingBackend:
        def __init__(self):
            self.hosts = []

        async def connect_tcp(self, host, port, **kwargs):
            self.hosts.append(host)
            if host == "8.8.8.8":
                raise httpcore.ConnectError("unavailable")
            return host, port

    backend = _PinnedMcpNetworkBackend("mcp.example.com", ["8.8.8.8", "1.1.1.1"])
    recorder = RecordingBackend()
    backend._backend = recorder

    result = await backend.connect_tcp("mcp.example.com", 443)

    assert result == ("1.1.1.1", 443)
    assert recorder.hosts == ["8.8.8.8", "1.1.1.1"]
    with pytest.raises(httpcore.ConnectError, match="unvalidated host"):
        await backend.connect_tcp("rebound.example.com", 443)
