"""Unit tests for historical trajectory calculation in ProjectNetWorthUseCase."""

from datetime import datetime
from decimal import Decimal

from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money
from paslood.use_cases.project_net_worth import ProjectNetWorthUseCase


def test_project_net_worth_default_starts_at_current_year():
    use_case = ProjectNetWorthUseCase()
    cur_yr = datetime.now().year
    res = use_case.execute(
        initial_assets=Money.from_val(100000.0),
        initial_debts=Money.from_val(20000.0),
        monthly_savings=Money.from_val(1000.0),
        annual_return_pct=Decimal("7.0"),
        years=5,
    )
    assert len(res) == 6
    assert res[0]["year"] == 0
    assert res[0]["calendar_year"] == cur_yr
    assert res[0]["is_historical"] is False
    assert res[0]["is_current"] is True
    assert res[0]["net_worth"] == Decimal("80000.00")
    assert res[5]["calendar_year"] == cur_yr + 5
    assert res[5]["is_historical"] is False


def test_project_net_worth_with_historical_start_year():
    use_case = ProjectNetWorthUseCase()
    cur_yr = datetime.now().year
    start_yr = cur_yr - 5  # 5 years in the past

    bs = BalanceSheet(
        assets=[
            Asset(
                id="prop-1",
                name="House",
                asset_class=AssetClass.REAL_ESTATE,
                current_value=Money.from_val(400000.0),
                cost_basis=Money.from_val(300000.0),
                acquisition_date=f"{start_yr}-01-01",
            )
        ],
        liabilities=[
            Liability(
                id="mort-1",
                name="Mortgage",
                loan_type=LoanType.MORTGAGE,
                principal_balance=Money.from_val(200000.0),
                start_capital=Money.from_val(250000.0),
                interest_rate_pct=Decimal("2.0"),
                start_date=f"{start_yr}-01-01",
                duration_months=240,
            )
        ],
    )

    res = use_case.execute(
        initial_assets=Money.from_val(400000.0),
        initial_debts=Money.from_val(200000.0),
        monthly_savings=Money.from_val(1000.0),
        annual_return_pct=Decimal("5.0"),
        years=10,
        start_year=start_yr,
        current_year=cur_yr,
        balance_sheet=bs,
    )

    # 5 historical years (start_yr to cur_yr - 1) + 1 current year + 10 future years = 16 points
    assert len(res) == 16
    first = res[0]
    assert first["calendar_year"] == start_yr
    assert first["is_historical"] is True
    assert first["is_current"] is False
    # At start_yr, asset was ~300000 cost basis, debt amortized from 250000 start capital to year-end balance
    assert abs(first["assets"] - Decimal("300000.00")) < Decimal("5000.00")
    assert Decimal("235000.00") <= first["debts"] <= Decimal("250000.00")

    # Current year point
    curr = res[5]
    assert curr["calendar_year"] == cur_yr
    assert curr["is_historical"] is False
    assert curr["is_current"] is True
    assert curr["assets"] == Decimal("400000.00")
    assert curr["debts"] == Decimal("200000.00")
    assert curr["net_worth"] == Decimal("200000.00")

    # Future point
    last = res[-1]
    assert last["calendar_year"] == cur_yr + 10
    assert last["is_historical"] is False
    assert last["net_worth"] > curr["net_worth"]


def test_project_net_worth_asset_acquired_midway():
    use_case = ProjectNetWorthUseCase()
    cur_yr = 2026
    start_yr = 2020

    bs = BalanceSheet(
        assets=[
            Asset(
                id="prop-1",
                name="Apartment",
                current_value=Money.from_val(300000.0),
                cost_basis=Money.from_val(250000.0),
                acquisition_date="2023-01-01",  # Acquired in 2023, not in 2020
            )
        ],
        liabilities=[],
    )

    res = use_case.execute(
        initial_assets=Money.from_val(300000.0),
        initial_debts=Money.from_val(0.0),
        monthly_savings=Money.from_val(500.0),
        years=5,
        start_year=start_yr,
        current_year=cur_yr,
        balance_sheet=bs,
    )

    # In 2020, 2021, 2022 asset should be 0.00
    by_year = {r["calendar_year"]: r for r in res}
    assert by_year[2020]["assets"] == Decimal("0.00")
    assert by_year[2021]["assets"] == Decimal("0.00")
    assert by_year[2022]["assets"] == Decimal("0.00")
    # In 2023, asset acquired at cost basis 250,000
    assert abs(by_year[2023]["assets"] - Decimal("250000.00")) < Decimal("2000.00")
    # In 2026, asset is 300,000
    assert by_year[2026]["assets"] == Decimal("300000.00")
