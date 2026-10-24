"""Tests for Internationalization (i18n) and Language Settings."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app


@pytest.fixture
def temp_config_repo():
    with TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "portfolio.yaml"
        repo = ConfigRepository(config_path=cfg_path)
        yield repo


@pytest.fixture
def test_app(temp_config_repo):
    return create_app(config_repo=temp_config_repo)


@pytest.mark.asyncio
async def test_get_i18n_endpoint(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/i18n")
        assert res.status_code == 200
        data = res.json()
        assert "supported_languages" in data
        assert "en" in data["supported_languages"]
        assert "nl" in data["supported_languages"]
        assert "translations" in data
        assert "nl" in data["translations"]
        assert "en" in data["translations"]
        assert data["translations"]["nl"]["nav"]["overview"] == "📊 Overzicht"


@pytest.mark.asyncio
async def test_get_i18n_specific_language(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/i18n/nl")
        assert res.status_code == 200
        data = res.json()
        assert data["language"] == "nl"
        assert "translations" in data
        assert data["translations"]["nav"]["overview"] == "📊 Overzicht"

        # Invalid language falls back to en or 404
        res_invalid = await client.get("/api/i18n/xx")
        assert res_invalid.status_code == 404


@pytest.mark.asyncio
async def test_settings_language_persistence(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default language should be "en"
        res = await client.get("/api/settings")
        assert res.status_code == 200
        settings = res.json()
        assert settings.get("language") == "en"

        # Update language to "nl"
        update_res = await client.post("/api/settings", json={"language": "nl"})
        assert update_res.status_code == 200
        assert update_res.json().get("status") in ("success", "updated")

        # Verify language is now "nl"
        res_after = await client.get("/api/settings")
        assert res_after.status_code == 200
        assert res_after.json().get("language") == "nl"


def test_config_repo_language(temp_config_repo):
    settings = temp_config_repo.load_settings()
    assert settings.get("language") == "en"

    temp_config_repo.save_settings({"language": "nl"})
    updated = temp_config_repo.load_settings()
    assert updated.get("language") == "nl"
