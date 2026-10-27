"""Tests for Security Hardening and Vulnerability Containment."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.delivery.web.app import create_app


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_security_headers_present(test_app):
    """Verify security headers (CSP, Frame Options, nosniff) are injected."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp


@pytest.mark.asyncio
async def test_ssrf_protection_blocks_cloud_metadata(test_app):
    """Verify SSRF defense rejects cloud metadata and link-local addresses."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. AWS/GCP Cloud Metadata IP
        resp_meta = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert resp_meta.status_code == 403
        assert "metadata" in resp_meta.json()["detail"].lower()

        # 2. Google metadata hostname
        resp_gcp = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "http://metadata.google.internal/computeMetadata/v1/"},
        )
        assert resp_gcp.status_code == 403


@pytest.mark.asyncio
async def test_ssrf_protection_blocks_invalid_scheme(test_app):
    """Verify SSRF defense rejects non-http schemes like file:// and gopher://."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/settings/mcp/servers/test",
            json={"url": "file:///etc/passwd"},
        )
        assert resp.status_code == 400
        assert "scheme" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oauth_redirect_uri_hijack_rejected(test_app):
    """Verify that external redirect_uri in OAuth initialization is rejected."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # External domain attempt
        resp = await client.get("/api/auth/pdt/connect?redirect_uri=https://evil.com/callback")
        assert resp.status_code == 400
        assert "redirect_uri" in resp.json()["detail"].lower()

        # Valid local redirect_uri should succeed
        with patch(
            "paslood.adapters.ingestion.pdt_auth.PdtAuthManager.register_client",
            new_callable=AsyncMock,
            return_value="valid-client",
        ):
            resp_valid = await client.get(
                "/api/auth/pdt/connect?redirect_uri=http://localhost:8000/api/auth/pdt/callback"
            )
            assert resp_valid.status_code == 200
            assert "auth_url" in resp_valid.json()


@pytest.mark.asyncio
async def test_local_origin_protection_blocks_external_csrf(test_app):
    """Verify cross-origin state-changing requests from untrusted external origins are blocked."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Untrusted external origin on POST
        resp_blocked = await client.post(
            "/api/data/reset-cache",
            headers={"Origin": "https://malicious-website.com"},
        )
        assert resp_blocked.status_code == 403
        assert "cross-origin" in resp_blocked.json()["detail"].lower()

        # Trusted local origin should be permitted
        resp_allowed = await client.post(
            "/api/data/reset-cache",
            headers={"Origin": "http://localhost:8000"},
        )
        assert resp_allowed.status_code == 200


@pytest.mark.asyncio
async def test_ai_models_header_key_supported(test_app):
    """Verify AI models endpoint accepts API key via X-AI-API-Key header."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "paslood.adapters.ai.llm_client.UniversalAIAdvisorClient.fetch_available_models",
            new_callable=AsyncMock,
            return_value=[{"id": "test-model", "name": "Test Model"}],
        ) as mock_fetch:
            resp = await client.get(
                "/api/ai/models?provider=gemini",
                headers={"X-AI-API-Key": "header-secret-key"},
            )
            assert resp.status_code == 200
            mock_fetch.assert_called_once_with(provider="gemini", api_key="header-secret-key")


def test_config_repo_secure_file_permissions(tmp_path):
    """Verify ConfigRepository sets 0o600 permissions on sensitive files on POSIX systems."""
    import os
    import stat
    import sys

    if sys.platform == "win32":
        pytest.skip("POSIX permissions not applicable on Windows")

    cfg_file = tmp_path / "sub" / "portfolio.yaml"
    repo = ConfigRepository(config_path=cfg_file)

    # Check portfolio.yaml permissions
    mode = stat.S_IMODE(os.stat(cfg_file).st_mode)
    assert mode == 0o600

    # Check parent directory permissions
    dir_mode = stat.S_IMODE(os.stat(cfg_file.parent).st_mode)
    assert dir_mode == 0o700

    # Check token file permissions after saving tokens
    repo.save_pdt_tokens({"access_token": "token-test", "client_id": "c1"})
    token_file = cfg_file.parent / "pdt_auth.json"
    assert token_file.exists()
    tok_mode = stat.S_IMODE(os.stat(token_file).st_mode)
    assert tok_mode == 0o600
