"""Delivery tests for /api/projection with historical timeline support."""

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app


@pytest.fixture
def app_with_history(tmp_path):
    portfolio_yaml = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    rules_yaml = tmp_path / "rules.yaml"

    repo = ConfigRepository(portfolio_yaml, rules_yaml)
    db = LocalDbRepository(db_file)

    # Add historical mortgage from 2019
    repo.save_manual_liability(
        {
            "id": "mortgage-test",
            "name": "KBC Mortgage",
            "loan_type": "MORTGAGE",
            "start_capital": 250000.0,
            "principal_balance": 200000.0,
            "interest_rate_pct": 2.0,
            "monthly_payment": 1050.0,
            "start_date": "2019-03-01",
            "duration_months": 240,
        }
    )

    # Add historical real estate from 2019
    repo.save_manual_asset(
        {
            "id": "house-test",
            "name": "Leuven Residence",
            "asset_class": "REAL_ESTATE",
            "current_value": 450000.0,
            "cost_basis": 320000.0,
            "acquisition_date": "2019-03-01",
        }
    )

    app = create_app(config_repo=repo, local_db=db)
    return app


@pytest.mark.asyncio
async def test_api_projection_auto_detects_oldest_date(app_with_history):
    transport = ASGITransport(app=app_with_history)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/projection?years=10")
        assert res.status_code == 200
        data = res.json()

        assert data["start_year"] == 2019
        assert data["oldest_detected_year"] == 2019
        assert data["oldest_detected_date"] == "2019-03-01"

        trajectory = data["trajectory"]
        assert len(trajectory) > 10

        # Check earliest historical point
        first = trajectory[0]
        assert first["calendar_year"] == 2019
        assert first["is_historical"] is True
        assert first["is_current"] is False

        # Check current year point
        now_yr = datetime.now().year
        curr = next((t for t in trajectory if t["calendar_year"] == now_yr), None)
        assert curr is not None
        assert curr["is_current"] is True
        assert curr["is_historical"] is False


@pytest.mark.asyncio
async def test_api_projection_explicit_start_year_override(app_with_history):
    transport = ASGITransport(app=app_with_history)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/projection?years=5&start_year=2022")
        assert res.status_code == 200
        data = res.json()

        assert data["start_year"] == 2022
        first = data["trajectory"][0]
        assert first["calendar_year"] == 2022


@pytest.mark.asyncio
async def test_api_projection_disable_auto_detect(app_with_history):
    transport = ASGITransport(app=app_with_history)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/projection?years=5&auto_detect_start=false")
        assert res.status_code == 200
        data = res.json()

        now_yr = datetime.now().year
        assert data["start_year"] == now_yr
        first = data["trajectory"][0]
        assert first["calendar_year"] == now_yr
        assert first["is_current"] is True
