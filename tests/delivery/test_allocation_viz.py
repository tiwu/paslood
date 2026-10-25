"""Tests for Enhanced Allocation Visualizer and Drift Tolerance Display."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_allocation_visualizer_dom_elements(test_app):
    """Verify that the allocation visualizer contains bullet & drift mode toggles and containers."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        html = resp.text

        # Verify mode toggle buttons exist
        assert 'id="btn-alloc-mode-bullet"' in html
        assert 'id="btn-alloc-mode-drift"' in html
        assert "setAllocationVizMode(" in html

        # Verify bullet meter and drift containers exist
        assert 'id="bucket-meters-container"' in html
        assert 'id="bucket-drift-container"' in html
        assert 'id="bucket-excluded-section"' in html

        # Verify JS rendering handles tolerance bands and target markers
        assert "target-pin" in html
        assert "tolerance-zone" in html
        assert "renderBulletMeters" in html
        assert "renderDriftChart" in html


def test_i18n_locales_contain_allocation_keys():
    """Verify that all four locales (en, nl, fr, de) contain the required visualizer keys."""
    locales_dir = (
        Path(__file__).parents[2]
        / "src"
        / "wealth_pilot"
        / "delivery"
        / "web"
        / "static"
        / "locales"
    )
    required_keys = [
        "visualizer_title",
        "visualizer_subtitle",
        "mode_bullet",
        "mode_drift",
        "excluded_section_title",
        "tolerance_corridor",
        "rebalance_action_overweight",
        "rebalance_action_underweight",
        "rebalance_action_balanced",
    ]

    for lang in ["en", "nl", "fr", "de"]:
        locale_path = locales_dir / f"{lang}.json"
        assert locale_path.exists(), f"Locale file {lang}.json missing"
        with open(locale_path, encoding="utf-8") as f:
            data = json.load(f)
        buckets_sec = data.get("buckets", {})
        for k in required_keys:
            assert k in buckets_sec, f"Missing key '{k}' in {lang}.json under 'buckets'"


@pytest.mark.asyncio
async def test_overview_api_delivers_complete_drift_metrics(test_app):
    """Ensure /api/overview returns all required mathematical drift and tolerance fields."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "allocations" in data
        allocations = data["allocations"]
        assert len(allocations) > 0

        for alloc in allocations:
            assert "bucket_id" in alloc
            assert "name" in alloc
            assert "current_value" in alloc
            assert "current_weight_pct" in alloc
            assert "target_weight_pct" in alloc
            assert "diff_value" in alloc
            assert "diff_weight_pct" in alloc
            assert "drift_status" in alloc
            assert "drift_tolerance_pct" in alloc
            assert "include_in_rebalancing" in alloc
