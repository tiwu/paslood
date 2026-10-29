"""Unit tests for FindOldestDateUseCase."""

from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import BalanceSheet
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money
from paslood.use_cases.find_oldest_date import FindOldestDateUseCase


def test_find_oldest_date_from_liability():
    bs = BalanceSheet(
        assets=[Asset(id="1", name="Cash", current_value=Money.from_val(1000.0))],
        liabilities=[
            Liability(
                id="mortgage-1",
                name="Home Loan",
                loan_type=LoanType.MORTGAGE,
                start_date="2018-05-10",
                start_capital=Money.from_val(250000.0),
            )
        ],
    )
    use_case = FindOldestDateUseCase()
    res = use_case.execute(bs)
    assert res["oldest_date"] == "2018-05-10"
    assert res["oldest_year"] == 2018


def test_find_oldest_date_from_asset():
    bs = BalanceSheet(
        assets=[
            Asset(
                id="1",
                name="Family Home",
                asset_class=AssetClass.REAL_ESTATE,
                current_value=Money.from_val(400000.0),
                acquisition_date="2016-09-01",
            )
        ],
        liabilities=[],
    )
    use_case = FindOldestDateUseCase()
    res = use_case.execute(bs)
    assert res["oldest_date"] == "2016-09-01"
    assert res["oldest_year"] == 2016


def test_find_oldest_date_from_transactions():
    bs = BalanceSheet(assets=[], liabilities=[])
    use_case = FindOldestDateUseCase()
    res = use_case.execute(bs, oldest_tx_date="2019-01-15")
    assert res["oldest_date"] == "2019-01-15"
    assert res["oldest_year"] == 2019


def test_find_oldest_date_chooses_minimum():
    bs = BalanceSheet(
        assets=[Asset(id="1", name="House", acquisition_date="2017-03-01")],
        liabilities=[Liability(id="l1", name="Loan", start_date="2015-11-20")],
    )
    use_case = FindOldestDateUseCase()
    res = use_case.execute(bs, oldest_tx_date="2020-04-01")
    assert res["oldest_date"] == "2015-11-20"
    assert res["oldest_year"] == 2015


def test_find_oldest_date_empty():
    bs = BalanceSheet(assets=[], liabilities=[])
    use_case = FindOldestDateUseCase()
    res = use_case.execute(bs)
    assert res["oldest_date"] is None
    assert res["oldest_year"] is None
