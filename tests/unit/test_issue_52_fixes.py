"""Unit tests for Issue #52 fixes and enhancements."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from paslood.adapters.repositories.config_repo import ConfigRepository
from paslood.adapters.repositories.local_db import LocalDbRepository
from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import BalanceSheet, Money, Transaction, TransactionCategory
from paslood.domain.bucket import Bucket
from paslood.use_cases.build_overview import BuildPortfolioOverviewUseCase
from paslood.use_cases.categorize_transactions import CategorizeTransactionsUseCase


def test_overview_includes_asset_acquisition_date_and_cost_basis() -> None:
    """Finding 1: BuildPortfolioOverviewUseCase must serialize acquisition_date and cost_basis on assets."""
    asset = Asset(
        id="asset-house",
        name="Family Residence",
        symbol="HOUSE",
        asset_class=AssetClass.REAL_ESTATE,
        current_value=Money(Decimal("450000.00")),
        cost_basis=Money(Decimal("320000.00")),
        acquisition_date="2019-06-15",
        institution="Manual",
    )
    bs = BalanceSheet(assets=[asset])
    buckets = [
        Bucket(id="core-etf", name="Core ETF", target_weight_pct=Decimal("100.0")),
    ]
    use_case = BuildPortfolioOverviewUseCase()
    result = use_case.execute(balance_sheet=bs, buckets=buckets)

    assert len(result["assets"]) == 1
    serialized_asset = result["assets"][0]
    assert serialized_asset["acquisition_date"] == "2019-06-15"
    assert serialized_asset["cost_basis"] == 320000.0
    assert serialized_asset["cost_basis_formatted"] == "€ 320.000,00"


def test_config_repo_save_manual_asset_preserves_and_serializes_cost_basis_and_date(
    tmp_path: Path,
) -> None:
    """Finding 1: ConfigRepository.save_manual_asset must persist Decimal cost_basis and acquisition_date cleanly."""
    repo = ConfigRepository(config_path=tmp_path / "portfolio.yaml")
    repo.save_manual_asset(
        {
            "id": "asset-test-1",
            "name": "Apartment",
            "asset_class": "REAL_ESTATE",
            "current_value": Decimal("350000.00"),
            "cost_basis": Decimal("280000.00"),
            "acquisition_date": "2020-05-01",
            "institution": "Manual",
        }
    )

    loaded = repo.load_manual_assets()
    target = next((a for a in loaded if a.id == "asset-test-1"), None)
    assert target is not None
    assert target.acquisition_date == "2020-05-01"
    assert target.cost_basis is not None
    assert target.cost_basis.amount == Decimal("280000.00")


def test_categorize_transactions_matches_keyword_across_description_and_counterparty_and_amount() -> (
    None
):
    """Findings 3 & 4: Custom rules match across description/counterparty and support optional amount."""
    use_case = CategorizeTransactionsUseCase()

    rules = [
        {
            "match_field": "counterparty_name",
            "pattern": "MAANDELIJKSE SPARING",
            "target_category": "SAVINGS",
        },
        {
            "match_field": "any",
            "pattern": "TIM WUYTENS",
            "amount": 500.0,
            "target_category": "INVESTMENTS",
        },
        {
            "match_field": "any",
            "pattern": "TIM WUYTENS",
            "amount": 150.0,
            "target_category": "SAVINGS",
        },
    ]

    # tx1 has counterparty_name="KBC" (non-empty!), but description has "MAANDELIJKSE SPARING"
    tx1 = Transaction(
        id="tx-1",
        date="2026-05-01",
        amount=Money(Decimal("-250.00")),
        account_id="BE90735017192832",
        description="DOORSTAANDE OPDRACHT MAANDELIJKSE SPARING",
        counterparty_name="KBC BANK",
    )
    # tx2 and tx3 have same counterparty "TIM WUYTENS" but different amounts (-500 vs -150)
    tx2 = Transaction(
        id="tx-2",
        date="2026-05-02",
        amount=Money(Decimal("-500.00")),
        account_id="BE90735017192832",
        description="Overschrijving",
        counterparty_name="TIM WUYTENS",
    )
    tx3 = Transaction(
        id="tx-3",
        date="2026-05-03",
        amount=Money(Decimal("-150.00")),
        account_id="BE90735017192832",
        description="Overschrijving",
        counterparty_name="TIM WUYTENS",
    )

    res = use_case.execute([tx1, tx2, tx3], rules=rules)
    assert res[0].category == TransactionCategory.SAVINGS.value
    assert res[1].category == TransactionCategory.INVESTMENTS.value
    assert res[2].category == TransactionCategory.SAVINGS.value


def test_local_db_apply_rule_with_amount(tmp_path: Path) -> None:
    """Finding 4: LocalDbRepository.apply_rule_to_transactions supports optional amount matching."""
    db = LocalDbRepository(db_path=tmp_path / "test.db")
    tx1 = Transaction(
        id="tx-a1",
        date="2026-05-01",
        amount=Money(Decimal("-500.00")),
        account_id="BE90735017192832",
        description="Transfer to Partner",
        counterparty_name="PARTNER ACCOUNT",
        category="LIVING_EXPENSES",
    )
    tx2 = Transaction(
        id="tx-a2",
        date="2026-05-02",
        amount=Money(Decimal("-120.00")),
        account_id="BE90735017192832",
        description="Transfer to Partner",
        counterparty_name="PARTNER ACCOUNT",
        category="LIVING_EXPENSES",
    )
    db.save_transactions([tx1, tx2], source="kbc_csv")

    updated = db.apply_rule_to_transactions(
        "PARTNER ACCOUNT", "SAVINGS", exclude_overrides=False, amount=Decimal("500.00")
    )
    assert updated == 1

    txs = {t.id: t for t in db.get_transactions()}
    assert txs["tx-a1"].category == "SAVINGS"
    assert txs["tx-a2"].category == "LIVING_EXPENSES"


def test_internal_transfers_between_accounts_recognized_as_saving_or_investing() -> None:
    """Finding 5: Internal transfers to own savings/bunq or investment accounts are recognized as SAVINGS/INVESTMENTS."""
    use_case = CategorizeTransactionsUseCase()

    tx_to_bunq = Transaction(
        id="tx-bunq-1",
        date="2026-06-01",
        amount=Money(Decimal("-1000.00")),
        account_id="BE90735017192832",
        description="Overschrijving naar eigen rekening",
        counterparty_name="T. Wuytens",
        counterparty_iban="NL28BUNQ2120824827",
    )
    tx_to_kbc_spaar = Transaction(
        id="tx-spaar-1",
        date="2026-06-02",
        amount=Money(Decimal("-500.00")),
        account_id="BE90735017192832",
        description="Interne overschrijving KBC-Spaarrekening",
        counterparty_name="Eigen rekening",
        counterparty_iban="BE45735099998888",
    )
    tx_to_bolero = Transaction(
        id="tx-bolero-1",
        date="2026-06-03",
        amount=Money(Decimal("-1500.00")),
        account_id="BE90735017192832",
        description="Eigen rekening Bolero beleggingsrekening",
        counterparty_name="Eigen rekening",
        counterparty_iban="BE11735011112222",
    )

    res = use_case.execute([tx_to_bunq, tx_to_kbc_spaar, tx_to_bolero])
    assert res[0].category == TransactionCategory.SAVINGS.value
    assert res[1].category == TransactionCategory.SAVINGS.value
    assert res[2].category == TransactionCategory.INVESTMENTS.value


def test_monthly_cashflow_period_selection_last_year_vs_all_time(tmp_path: Path) -> None:
    """Finding 8: get_monthly_cashflow supports period='year' (last 12 months) vs period='all'."""
    db = LocalDbRepository(db_path=tmp_path / "test.db")
    txs = [
        # Old transaction from 2024 (high income & high expense)
        Transaction(
            id="tx-old-inc",
            date="2024-01-15",
            amount=Money(Decimal("10000.00")),
            account_id="BE90",
            description="Salary 2024",
            category="INCOME",
        ),
        Transaction(
            id="tx-old-exp",
            date="2024-01-20",
            amount=Money(Decimal("-4000.00")),
            account_id="BE90",
            description="Shopping 2024",
            category="LIVING_EXPENSES",
        ),
        # Recent transaction from 2026-09 (normal income & expense)
        Transaction(
            id="tx-new-inc",
            date="2026-09-15",
            amount=Money(Decimal("5000.00")),
            account_id="BE90",
            description="Salary 2026",
            category="INCOME",
        ),
        Transaction(
            id="tx-new-exp",
            date="2026-09-20",
            amount=Money(Decimal("-1000.00")),
            account_id="BE90",
            description="Groceries 2026",
            category="GROCERIES",
        ),
    ]
    db.save_transactions(txs, source="kbc_csv")

    cf_all = db.get_monthly_cashflow(period="all")
    cf_year = db.get_monthly_cashflow(period="year")

    assert cf_all.months_analyzed == 2
    assert cf_all.monthly_income.amount == Decimal("7500.00")
    assert cf_all.period == "all"

    assert cf_year.months_analyzed == 1
    assert cf_year.monthly_income.amount == Decimal("5000.00")
    assert cf_year.living_expenses.amount == Decimal("1000.00")
    assert cf_year.period == "year"


def test_overview_auto_detects_historical_start_year_on_initial_load() -> None:
    """Finding 9: BuildPortfolioOverviewUseCase.execute auto-detects historical start_year on page load."""
    asset = Asset(
        id="asset-etf",
        name="World ETF",
        symbol="VWCE",
        asset_class=AssetClass.ETF,
        current_value=Money(Decimal("100000.00")),
        cost_basis=Money(Decimal("60000.00")),
        acquisition_date="2020-01-15",
    )
    bs = BalanceSheet(assets=[asset])
    buckets = [Bucket(id="core-etf", name="Core ETF", target_weight_pct=Decimal("100.0"))]

    use_case = BuildPortfolioOverviewUseCase()
    data = use_case.execute(balance_sheet=bs, buckets=buckets)

    now_yr = datetime.now().year
    assert data["oldest_detected_year"] == 2020
    assert data["current_year"] == now_yr
    assert data["trajectory"][0]["calendar_year"] == 2020
    assert data["trajectory"][0]["is_historical"] is True
    assert any(
        pt["is_current"] is True and pt["calendar_year"] == now_yr for pt in data["trajectory"]
    )
