"""Tests for Internationalization (i18n), Isolated Locale Files, and Language Settings."""

from __future__ import annotations

import json
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


def test_isolated_locale_files_exist_and_have_key_parity():
    locales_dir = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "wealth_pilot"
        / "delivery"
        / "web"
        / "static"
        / "locales"
    )
    assert locales_dir.exists(), "static/locales directory must exist"

    expected_langs = ["en", "nl", "fr", "de"]
    loaded: dict[str, dict] = {}
    for lang in expected_langs:
        file_path = locales_dir / f"{lang}.json"
        assert file_path.exists(), f"Locale file {lang}.json must exist"
        loaded[lang] = json.loads(file_path.read_text(encoding="utf-8"))

    required_sections = {
        "header",
        "nav",
        "dashboard",
        "buckets",
        "guidance",
        "cashflow",
        "ai",
        "settings",
        "modals",
        "advice_items",
        "priority",
        "common",
    }
    en_data = loaded["en"]
    assert required_sections.issubset(set(en_data.keys()))

    # Verify key parity across all languages
    for lang in ["nl", "fr", "de"]:
        lang_data = loaded[lang]
        for section in required_sections:
            assert section in lang_data, f"Missing section '{section}' in {lang}.json"
            assert set(en_data[section].keys()) == set(lang_data[section].keys()), (
                f"Key mismatch in section '{section}' for {lang}.json"
            )


@pytest.mark.asyncio
async def test_static_locale_file_serving_and_full_page_i18n_attributes(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Static JSON file serving
        res_nl = await client.get("/static/locales/nl.json")
        assert res_nl.status_code == 200
        nl_json = res_nl.json()
        assert nl_json["nav"]["overview"] == "📊 Overzicht"
        assert nl_json["dashboard"]["kpi_net_worth"] == "Totale Nettowaarde"

        # Verify index.html has data-i18n attributes across all tabs and modals
        res_html = await client.get("/")
        assert res_html.status_code == 200
        html = res_html.text
        for prefix in [
            'data-i18n="dashboard.',
            'data-i18n="buckets.',
            'data-i18n="guidance.',
            'data-i18n="cashflow.',
            'data-i18n="ai.',
            'data-i18n="settings.',
            'data-i18n="modals.',
        ]:
            assert prefix in html, f"Expected {prefix} in index.html"


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
        assert data["translations"]["nl"]["dashboard"]["kpi_net_worth"] == "Totale Nettowaarde"


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

        # Invalid language returns 404
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
