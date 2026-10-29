"""Delivery test for Cashflow overview serialization and pagination (#39)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.delivery.web.app import create_app
from paslood.domain.balance_sheet import Money, Transaction


@pytest.mark.asyncio
async def test_overview_includes_account_id_and_large_history(tmp_path: Path) -> None:
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)

    # Insert 150 transactions across 2 accounts
    txs = []
    for i in range(150):
        acc = "BE90735017192832" if i % 2 == 0 else "NL31BUNQ2093809982"
        txs.append(
            Transaction(
                id=f"tx-{i}",
                date="2026-05-01",
                amount=Money(Decimal("-10.00")),
                account_id=acc,
                description=f"Transaction {i}",
                counterparty_name="Merchant",
                category="GROCERIES",
            )
        )
    db.save_transactions(txs, source="test")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/overview")
        assert res.status_code == 200
        data = res.json()
        assert len(data["transactions"]) == 150
        first_tx = data["transactions"][0]
        assert "account_id" in first_tx
        assert first_tx["account_id"] in ("BE90735017192832", "NL31BUNQ2093809982")


@pytest.mark.asyncio
async def test_overview_includes_cashflow_breakdown_sankey_and_monthly_spending(
    tmp_path: Path,
) -> None:
    """Verify /api/overview exposes cashflow_breakdown (explaining Free Monthly Cashflow)
    and cashflow_analytics (Sankey flow links and monthly spending & savings potential).
    """
    config_file = tmp_path / "portfolio.yaml"
    db_file = tmp_path / "paslood.db"
    repo = ConfigRepository(config_path=config_file)
    db = LocalDbRepository(db_path=db_file)

    txs = [
        Transaction(
            id="tx-inc-1",
            date="2026-05-01",
            amount=Money(Decimal("5000.00")),
            account_id="BE90735017192832",
            description="Salaris Mei",
            counterparty_name="Employer NV",
            category="INCOME",
        ),
        Transaction(
            id="tx-mort-1",
            date="2026-05-02",
            amount=Money(Decimal("-1100.00")),
            account_id="BE90735017192832",
            description="Woningkrediet",
            counterparty_name="KBC",
            category="MORTGAGE",
        ),
        Transaction(
            id="tx-util-1",
            date="2026-05-05",
            amount=Money(Decimal("-200.00")),
            account_id="BE90735017192832",
            description="Elektriciteit",
            counterparty_name="Engie",
            category="UTILITIES",
        ),
        Transaction(
            id="tx-tax-1",
            date="2026-05-06",
            amount=Money(Decimal("-150.00")),
            account_id="BE90735017192832",
            description="Gemeentebelasting",
            counterparty_name="FOD Financien",
            category="TAX",
        ),
        Transaction(
            id="tx-groc-1",
            date="2026-05-10",
            amount=Money(Decimal("-450.00")),
            account_id="BE90735017192832",
            description="Boodschappen",
            counterparty_name="Colruyt",
            category="GROCERIES",
        ),
        Transaction(
            id="tx-leis-1",
            date="2026-05-12",
            amount=Money(Decimal("-300.00")),
            account_id="BE90735017192832",
            description="Uit eten",
            counterparty_name="Restaurant",
            category="LEISURE",
        ),
        Transaction(
            id="tx-inv-1",
            date="2026-05-15",
            amount=Money(Decimal("-1500.00")),
            account_id="BE90735017192832",
            description="Belegging ETF",
            counterparty_name="Saxo",
            category="INVESTMENTS",
        ),
    ]
    db.save_transactions(txs, source="kbc_csv")

    app = create_app(config_repo=repo, local_db=db)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/overview")
        assert res.status_code == 200
        data = res.json()

        # 1. Verify cashflow_breakdown explains how free_cashflow_value is calculated
        assert "cashflow_breakdown" in data
        cb = data["cashflow_breakdown"]
        assert cb["monthly_income"] == 5000.0
        assert cb["fixed_costs"] == 350.0  # 200 UTILITIES + 150 TAX
        assert cb["debt_payments"] == 1100.0  # 1100 MORTGAGE
        assert cb["living_expenses"] == 750.0  # 450 GROCERIES + 300 LEISURE
        assert cb["free_cashflow"] == 2800.0  # 5000 - (350 + 1100 + 750)
        assert data["free_cashflow_value"] == 2800.0

        # 2. Verify cashflow_analytics provides Sankey flow and monthly spending / savings potential
        assert "cashflow_analytics" in data
        analytics = data["cashflow_analytics"]
        assert "sankey" in analytics
        assert len(analytics["sankey"]["links"]) >= 3
        assert "monthly_spending" in analytics
        assert len(analytics["monthly_spending"]) == 1
        assert analytics["monthly_spending"][0]["month"] == "2026-05"
        assert "savings_opportunities" in analytics
        assert len(analytics["savings_opportunities"]) >= 1
