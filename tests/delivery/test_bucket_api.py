"""Delivery tests for bucket target weight API validation."""

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.delivery.web.app import create_app


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


@pytest.mark.asyncio
async def test_update_single_bucket_target_validation(test_app):
    """Test that /api/buckets/target enforces 100% total weight across active buckets."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initial default sum is 50 + 35 + 5 + 10 = 100%
        # Updating core-etf to 55% causes total to be 105% -> expect 400
        res_fail = await client.post(
            "/api/buckets/target",
            json={"bucket_id": "core-etf", "name": "Core World ETFs", "target_weight_pct": 55.0},
        )
        assert res_fail.status_code == 400
        assert "must sum to 100%" in res_fail.json()["detail"]

        # Updating core-etf to 50% maintains 100% total -> expect 200
        res_ok = await client.post(
            "/api/buckets/target",
            json={"bucket_id": "core-etf", "name": "Core World ETFs", "target_weight_pct": 50.0},
        )
        assert res_ok.status_code == 200
        assert res_ok.json() == {"status": "success"}


@pytest.mark.asyncio
async def test_batch_update_bucket_targets(test_app):
    """Test that /api/buckets/targets allows atomic reallocation summing to 100%."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unbalanced batch targets (sum = 110%) -> expect 400
        res_fail = await client.post(
            "/api/buckets/targets",
            json={
                "targets": {
                    "core-etf": 55.0,
                    "tech-growth": 40.0,
                    "commodities": 5.0,
                    "cash-buffer": 10.0,
                }
            },
        )
        assert res_fail.status_code == 400
        assert "must sum to 100%" in res_fail.json()["detail"]

        # Balanced batch targets (sum = 100%: 55 + 30 + 5 + 10) -> expect 200
        res_ok = await client.post(
            "/api/buckets/targets",
            json={
                "targets": {
                    "core-etf": 55.0,
                    "tech-growth": 30.0,
                    "commodities": 5.0,
                    "cash-buffer": 10.0,
                }
            },
        )
        assert res_ok.status_code == 200
        assert res_ok.json() == {"status": "success"}

        # Verify new weights reflected in overview
        overview_res = await client.get("/api/overview")
        assert overview_res.status_code == 200
        allocations = {
            a["bucket_id"]: a["target_weight_pct"] for a in overview_res.json()["allocations"]
        }
        assert allocations["core-etf"] == 55.0
        assert allocations["tech-growth"] == 30.0


@pytest.mark.asyncio
async def test_assign_bunq_savings_account_to_cash_buffer_and_option_a_filtering(tmp_path):
    """Test Option A cash filtering (only SAVINGS accounts in Cash Buffer, CHECKING & PDT cash excluded)
    and verify assigning an unassigned Bunq account to 'cash-buffer' via asset_name persists properly.
    """
    from decimal import Decimal

    from paslood.adapters.repositories.local_db import LocalDbRepository
    from paslood.domain.account import KnownAccount
    from paslood.domain.asset import Asset, AssetClass
    from paslood.domain.money import Money

    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    db = LocalDbRepository(db_path=tmp_path / "paslood.db")

    # Customize cash-buffer bucket so it doesn't have default catch-all CASH rule (simulating user's unassigned bunq account)
    repo.save_bucket(
        {
            "id": "cash-buffer",
            "name": "Cash & Emergency Buffer",
            "target_weight_pct": 10.0,
            "rules": [{"name_keywords": ["EMERGENCY_RESERVE"]}],
        }
    )

    # Register Known Accounts: one CHECKING, one SAVINGS
    repo.save_known_account(
        KnownAccount(
            id="ka-checking",
            account_number="BE90 7350 1719 2832",
            label="KBC Spending",
            account_type="CHECKING",
            institution="KBC",
        )
    )
    repo.save_known_account(
        KnownAccount(
            id="ka-bunq-sav",
            account_number="NL28 BUNQ 2120 8248 27",
            label="Bunq Savings",
            account_type="SAVINGS",
            institution="bunq",
        )
    )

    # Save discovered assets:
    # 1. KBC Checking (should be excluded by Option A because it's CHECKING)
    # 2. PDT Broker Cash (should be excluded by Option A because it's noisy broker cash)
    # 3. Bunq Savings (should be included as a holding, initially unassigned due to custom rule above)
    # 4. VWCE ETF (investment holding)
    db.save_discovered_assets(
        [
            Asset(
                id="kbc-checking-BE90735017192832",
                name="KBC Checking (BE90735017192832)",
                symbol="CASH",
                asset_class=AssetClass.CASH,
                current_value=Money(Decimal("2100.00")),
                institution="KBC",
                account_id="BE90735017192832",
            ),
            Asset(
                id="pdt-cash-eur",
                name="CASH",
                symbol="CASH",
                asset_class=AssetClass.CASH,
                current_value=Money(Decimal("145.50")),
                institution="PDT Portfolio",
            ),
            Asset(
                id="bunq-cash-NL28BUNQ2120824827",
                name="bunq (NL28BUNQ2120824827)",
                symbol="CASH",
                asset_class=AssetClass.CASH,
                current_value=Money(Decimal("5000.00")),
                institution="bunq",
                account_id="NL28BUNQ2120824827",
            ),
            Asset(
                id="pdt-vwce",
                name="Vanguard FTSE All-World",
                symbol="VWCE",
                isin="IE00BK5BQT80",
                asset_class=AssetClass.ETF,
                current_value=Money(Decimal("45000.00")),
                institution="PDT Portfolio",
            ),
        ],
        source="test",
    )

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ov1 = (await client.get("/api/overview")).json()
        asset_ids = [a["id"] for a in ov1["assets"]]

        # Option A: KBC Checking and PDT Broker Cash are excluded from strategic holdings
        assert "kbc-checking-BE90735017192832" not in asset_ids
        assert "pdt-cash-eur" not in asset_ids
        # Bunq Savings and VWCE are present
        assert "bunq-cash-NL28BUNQ2120824827" in asset_ids
        assert "pdt-vwce" in asset_ids

        bunq_asset = next(a for a in ov1["assets"] if a["id"] == "bunq-cash-NL28BUNQ2120824827")
        assert bunq_asset["bucket_id"] == "unassigned"

        # Now assign the Bunq account to 'cash-buffer' using the exact payload sent by buckets.js (`asset_name` + `symbol: "CASH"`)
        assign_res = await client.post(
            "/api/buckets/assign-asset",
            json={
                "bucket_id": "cash-buffer",
                "symbol": "CASH",
                "isin": None,
                "asset_id": "bunq-cash-NL28BUNQ2120824827",
                "asset_name": "bunq (NL28BUNQ2120824827)",
            },
        )
        assert assign_res.status_code == 200

        # Verify in /api/overview that the Bunq account is now assigned to 'cash-buffer'!
        ov2 = (await client.get("/api/overview")).json()
        bunq_asset_after = next(
            a for a in ov2["assets"] if a["id"] == "bunq-cash-NL28BUNQ2120824827"
        )
        assert bunq_asset_after["bucket_id"] == "cash-buffer"
        assert bunq_asset_after["bucket_name"] == "Cash & Emergency Buffer"
