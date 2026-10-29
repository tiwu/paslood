"""Delivery integration tests for Issue #52 endpoints and HTML/UI contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app
from paslood.domain.balance_sheet import Money, Transaction


@pytest.mark.asyncio
async def test_manual_asset_date_and_cost_basis_saved_and_returned_in_overview(
    tmp_path: Path,
) -> None:
    """Finding 1: Saving an asset with acquisition_date and cost_basis returns them in /api/overview."""
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "paslood.db")
    app = create_app(config_repo=repo, local_db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post_res = await client.post(
            "/api/assets/manual",
            json={
                "id": "asset-house-1",
                "name": "Family Home",
                "asset_class": "REAL_ESTATE",
                "current_value": 475000.0,
                "cost_basis": 340000.0,
                "acquisition_date": "2019-08-01",
                "institution": "Manual",
            },
        )
        assert post_res.status_code == 200

        ov_res = await client.get("/api/overview")
        assert ov_res.status_code == 200
        ov_data = ov_res.json()

        house = next((a for a in ov_data["assets"] if a["id"] == "asset-house-1"), None)
        assert house is not None
        assert house["acquisition_date"] == "2019-08-01"
        assert house["cost_basis"] == 340000.0

        # Compound wealth graph on initial overview load must start at 2019 (Finding 9)
        assert ov_data["oldest_detected_year"] == 2019
        assert ov_data["trajectory"][0]["calendar_year"] == 2019
        assert ov_data["trajectory"][0]["is_historical"] is True
        now_yr = datetime.now().year
        assert any(t["calendar_year"] == now_yr and t["is_current"] for t in ov_data["trajectory"])


@pytest.mark.asyncio
async def test_rebucket_with_custom_keyword_and_amount(tmp_path: Path) -> None:
    """Findings 3 & 4: Re-bucketing with custom keyword and optional amount saves and updates matching rows only."""
    repo = ConfigRepository(tmp_path / "portfolio.yaml", tmp_path / "rules.yaml")
    db = LocalDbRepository(db_path=tmp_path / "paslood.db")

    tx1 = Transaction(
        id="tx-rb-1",
        date="2026-05-01",
        amount=Money(Decimal("-250.00")),
        account_id="BE90",
        description="DOORSTAANDE OPDRACHT SPARING KINDEREN",
        counterparty_name="KBC",
        category="LIVING_EXPENSES",
    )
    tx2 = Transaction(
        id="tx-rb-2",
        date="2026-06-01",
        amount=Money(Decimal("-250.00")),
        account_id="BE90",
        description="DOORSTAANDE OPDRACHT SPARING KINDEREN",
        counterparty_name="KBC",
        category="LIVING_EXPENSES",
    )
    tx3 = Transaction(
        id="tx-rb-3",
        date="2026-06-02",
        amount=Money(Decimal("-75.00")),
        account_id="BE90",
        description="DOORSTAANDE OPDRACHT SPARING KINDEREN",
        counterparty_name="KBC",
        category="LIVING_EXPENSES",
    )
    db.save_transactions([tx1, tx2, tx3], source="kbc_csv")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/transactions/rebucket",
            json={
                "transaction_id": "tx-rb-1",
                "target_category": "SAVINGS",
                "pattern": "SPARING KINDEREN",
                "amount": 250.0,
                "remember_rule": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["updated_historical_count"] == 2

    txs = {t.id: t for t in db.get_transactions()}
    assert txs["tx-rb-1"].category == "SAVINGS"
    assert txs["tx-rb-2"].category == "SAVINGS"
    assert txs["tx-rb-3"].category == "LIVING_EXPENSES"

    rules = repo.load_transaction_rules()
    assert any(
        r.get("pattern") == "SPARING KINDEREN" and float(r.get("amount", 0)) == 250.0 for r in rules
    )


@pytest.mark.asyncio
async def test_overview_cashflow_period_query_param(tmp_path: Path) -> None:
    """Findings 7 & 8: /api/overview supports cashflow_period='year' vs 'all'."""
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "paslood.db")
    db.save_transactions(
        [
            Transaction(
                id="tx-2024",
                date="2024-03-10",
                amount=Money(Decimal("8000.00")),
                account_id="BE90",
                description="Bonus 2024",
                category="INCOME",
            ),
            Transaction(
                id="tx-2026",
                date="2026-08-10",
                amount=Money(Decimal("4000.00")),
                account_id="BE90",
                description="Salary 2026",
                category="INCOME",
            ),
        ],
        source="kbc_csv",
    )

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_all = await client.get("/api/overview?cashflow_period=all")
        res_yr = await client.get("/api/overview?cashflow_period=year")

        assert res_all.status_code == 200
        assert res_yr.status_code == 200

        data_all = res_all.json()
        data_yr = res_yr.json()

        assert data_all["cashflow_breakdown"]["months_analyzed"] == 2
        assert data_all["cashflow_breakdown"]["monthly_income"] == 6000.0
        assert data_all["cashflow_breakdown"]["period"] == "all"

        assert data_yr["cashflow_breakdown"]["months_analyzed"] == 1
        assert data_yr["cashflow_breakdown"]["monthly_income"] == 4000.0
        assert data_yr["cashflow_breakdown"]["period"] == "year"


@pytest.mark.asyncio
async def test_loan_and_asset_modal_inputs_use_step_any(tmp_path: Path) -> None:
    """Finding 2: Number inputs in loan and asset modals must not use restrictive step=25/100/1000."""
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "paslood.db")
    app = create_app(config_repo=repo, local_db=db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        html = res.text

        for input_id in [
            "manual-liab-start-cap",
            "manual-liab-balance",
            "manual-liab-rate",
            "manual-liab-payment",
            "manual-liab-payment-pct",
            "manual-asset-val",
            "manual-asset-cost-basis",
        ]:
            assert f'id="{input_id}"' in html
            # Find the input tag containing this id
            idx = html.index(f'id="{input_id}"')
            tag_slice = html[max(0, idx - 60) : idx + 150]
            assert 'step="any"' in tag_slice, (
                f"Input {input_id} should have step='any': {tag_slice}"
            )
