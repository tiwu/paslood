"""Tests for Local SQLite Database Repository (Layer 3 - Interface Adapters).
Verifies caching of transactions, assets, liabilities, and cumulative cashflow across multiple CSV imports.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from wealth_pilot.adapters.repositories.local_db import LocalDbRepository
from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.balance_sheet import Transaction
from wealth_pilot.domain.liability import Liability, LoanType
from wealth_pilot.domain.money import Money


@pytest.fixture
def local_db(tmp_path: Path) -> LocalDbRepository:
    db_file = tmp_path / "test_wealth_pilot.db"
    return LocalDbRepository(db_path=db_file)


def test_save_and_accumulate_transactions(local_db: LocalDbRepository):
    # Batch 1 (Month 1: January)
    tx1 = Transaction(
        id="tx-kbc-001",
        date="2026-01-15",
        amount=Money(Decimal("3000.00")),
        account_id="BE0012345678",
        description="Salary Company A",
        category="INCOME",
    )
    tx2 = Transaction(
        id="tx-kbc-002",
        date="2026-01-18",
        amount=Money(Decimal("-50.00")),
        account_id="BE0012345678",
        description="Delhaize Supermarket",
        category="GROCERIES",
    )

    added = local_db.save_transactions([tx1, tx2], source="kbc_csv")
    assert added == 2
    assert len(local_db.get_transactions()) == 2

    # Batch 2 (Month 2: February) - with one duplicate tx1 and one new tx3
    tx3 = Transaction(
        id="tx-kbc-003",
        date="2026-02-15",
        amount=Money(Decimal("3000.00")),
        account_id="BE0012345678",
        description="Salary Company A",
        category="INCOME",
    )

    added2 = local_db.save_transactions([tx1, tx3], source="kbc_csv")
    assert added2 == 1  # tx1 ignored as duplicate, tx3 added

    # Total accumulated transactions should be 3
    all_txs = local_db.get_transactions()
    assert len(all_txs) == 3
    # Sorted newest first
    assert all_txs[0].id == "tx-kbc-003"
    assert all_txs[1].id == "tx-kbc-002"
    assert all_txs[2].id == "tx-kbc-001"


def test_update_transaction_category(local_db: LocalDbRepository):
    tx = Transaction(
        id="tx-rebucket-001",
        date="2026-02-01",
        amount=Money(Decimal("-120.00")),
        account_id="BE0012345678",
        description="Restaurant Chez Leon",
        category="UNCATEGORIZED",
    )
    local_db.save_transactions([tx])

    updated = local_db.update_transaction_category("tx-rebucket-001", "DINING_OUT")
    assert updated is True

    stored = local_db.get_transactions()
    assert stored[0].category == "DINING_OUT"


def test_discovered_assets_persistence(local_db: LocalDbRepository):
    asset_checking = Asset(
        id="kbc-cash-be001",
        name="KBC Checking",
        asset_class=AssetClass.CASH,
        current_value=Money(Decimal("4500.00")),
        institution="KBC",
        account_id="BE0012345678",
    )
    local_db.save_discovered_assets([asset_checking], source="kbc_csv")

    # Ingest a second file with another account (e.g. savings account)
    asset_savings = Asset(
        id="kbc-savings-be002",
        name="KBC Savings",
        asset_class=AssetClass.CASH,
        current_value=Money(Decimal("12000.00")),
        institution="KBC",
        account_id="BE9988776655",
    )
    local_db.save_discovered_assets([asset_savings], source="kbc_csv")

    assets = local_db.get_discovered_assets()
    assert len(assets) == 2
    ids = {a.id for a in assets}
    assert "kbc-cash-be001" in ids
    assert "kbc-savings-be002" in ids


def test_discovered_liabilities_preserves_user_edits(local_db: LocalDbRepository):
    # CSV import detects loan monthly payment with unknown balance (0.00) and rate (0.00)
    csv_loan = Liability(
        id="mortgage-420-1111111-22",
        name="Woningkrediet (420-1111111-22)",
        loan_type=LoanType.MORTGAGE,
        principal_balance=Money(Decimal("0.00")),
        interest_rate_pct=Decimal("0.00"),
        monthly_payment=Money(Decimal("650.00")),
        institution="KBC",
        account_reference="420-1111111-22",
    )
    local_db.save_discovered_liabilities([csv_loan])

    liabs = local_db.get_discovered_liabilities()
    assert len(liabs) == 1
    assert liabs[0].principal_balance.amount == Decimal("0.00")
    assert liabs[0].monthly_payment.amount == Decimal("650.00")

    # User edits liability with their actual remaining principal and actual mortgage APR
    local_db.update_liability(
        liability_id="mortgage-420-1111111-22",
        updates={
            "principal_balance": 185000.00,
            "interest_rate_pct": 2.15,
            "monthly_payment": 650.00,
        },
    )

    edited_liabs = local_db.get_discovered_liabilities()
    assert edited_liabs[0].principal_balance.amount == Decimal("185000.00")
    assert edited_liabs[0].interest_rate_pct == Decimal("2.15")

    # Subsequent CSV import does NOT wipe out user-confirmed balance or APR!
    local_db.save_discovered_liabilities([csv_loan])
    preserved_liabs = local_db.get_discovered_liabilities()
    assert preserved_liabs[0].principal_balance.amount == Decimal("185000.00")
    assert preserved_liabs[0].interest_rate_pct == Decimal("2.15")
    assert preserved_liabs[0].monthly_payment.amount == Decimal("650.00")


def test_compute_cashflow_from_cumulative_transactions(local_db: LocalDbRepository):
    # 2 months of salary and expenses
    txs = [
        # Jan
        Transaction(
            id="t1",
            date="2026-01-25",
            amount=Money(Decimal("5000.00")),
            account_id="acc1",
            description="Salary",
            category="INCOME",
        ),
        Transaction(
            id="t2",
            date="2026-01-26",
            amount=Money(Decimal("-1000.00")),
            account_id="acc1",
            description="Rent",
            category="HOUSING",
        ),
        # Feb
        Transaction(
            id="t3",
            date="2026-02-25",
            amount=Money(Decimal("5000.00")),
            account_id="acc1",
            description="Salary",
            category="INCOME",
        ),
        Transaction(
            id="t4",
            date="2026-02-26",
            amount=Money(Decimal("-1000.00")),
            account_id="acc1",
            description="Rent",
            category="HOUSING",
        ),
    ]
    local_db.save_transactions(txs)

    cashflow = local_db.get_monthly_cashflow()
    assert cashflow.monthly_income.amount == Decimal("5000.00")
