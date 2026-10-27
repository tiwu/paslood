"""Unit tests for Paslood Domain Entities (Clean Architecture - Layer 1)."""

from decimal import Decimal

from paslood.domain.asset import Asset, AssetClass
from paslood.domain.balance_sheet import BalanceSheet, MonthlyCashflow
from paslood.domain.bucket import AllocationRule, Bucket
from paslood.domain.liability import Liability, LoanType
from paslood.domain.money import Money


def test_money_creation_and_arithmetic():
    m1 = Money(Decimal("100.50"), "EUR")
    m2 = Money(Decimal("50.25"), "EUR")

    assert m1.amount == Decimal("100.50")
    assert m1.currency == "EUR"
    assert (m1 + m2).amount == Decimal("150.75")
    assert (m1 - m2).amount == Decimal("50.25")
    assert (m1 * Decimal("2")).amount == Decimal("201.00")
    assert m1.format() == "€ 100,50"


def test_money_from_numeric_and_string():
    m1 = Money.from_val(1234.56, "EUR")
    assert m1.amount == Decimal("1234.56")
    assert m1.format() == "€ 1.234,56"

    m2 = Money.from_val("500,25", "EUR")
    assert m2.amount == Decimal("500.25")


def test_asset_and_bucket_assignment():
    asset1 = Asset(
        id="aapl",
        name="Apple Inc.",
        symbol="AAPL",
        isin="US0378331005",
        asset_class=AssetClass.EQUITY,
        current_value=Money.from_val(40000.0),
        quantity=Decimal("200.0"),
        institution="Broker",
    )

    asset2 = Asset(
        id="vwce",
        name="Vanguard FTSE All-World UCITS ETF",
        symbol="VWCE",
        isin="IE00BK5BQT80",
        asset_class=AssetClass.ETF,
        current_value=Money.from_val(50000.0),
        quantity=Decimal("400.0"),
        institution="DEGIRO",
    )

    bucket_core = Bucket(
        id="core-etf",
        name="Core Global ETFs",
        target_weight_pct=Decimal("50.0"),
        drift_tolerance_pct=Decimal("3.0"),
        rules=[
            AllocationRule(symbols={"VWCE"}, asset_classes={AssetClass.ETF}),
        ],
    )

    bucket_tech = Bucket(
        id="tech-conviction",
        name="High-Conviction Tech",
        target_weight_pct=Decimal("40.0"),
        drift_tolerance_pct=Decimal("3.0"),
        rules=[
            AllocationRule(symbols={"AAPL"}),
        ],
    )

    assert bucket_core.matches(asset2)
    assert not bucket_core.matches(asset1)
    assert bucket_tech.matches(asset1)
    assert not bucket_tech.matches(asset2)


def test_liability_and_debt():
    mortgage = Liability(
        id="kbc-mortgage-1",
        name="KBC Woningkrediet 1",
        loan_type=LoanType.MORTGAGE,
        principal_balance=Money.from_val(180000.0),
        interest_rate_pct=Decimal("1.85"),
        monthly_payment=Money.from_val(579.68),
        institution="KBC",
    )

    credit = Liability(
        id="kbc-flex",
        name="KBC Flex Budget",
        loan_type=LoanType.CONSUMER_LOAN,
        principal_balance=Money.from_val(5000.0),
        interest_rate_pct=Decimal("9.50"),
        monthly_payment=Money.from_val(309.60),
        institution="KBC",
    )

    assert mortgage.is_high_interest(threshold_pct=Decimal("5.0")) is False
    assert credit.is_high_interest(threshold_pct=Decimal("5.0")) is True


def test_balance_sheet_and_net_worth():
    assets = [
        Asset(
            id="a1",
            name="Investments",
            symbol="PORT",
            asset_class=AssetClass.EQUITY,
            current_value=Money.from_val(90000.0),
        ),
        Asset(
            id="a2",
            name="KBC Checking",
            symbol="CASH",
            asset_class=AssetClass.CASH,
            current_value=Money.from_val(2500.0),
        ),
        Asset(
            id="a3",
            name="Bunq Savings",
            symbol="SAVINGS",
            asset_class=AssetClass.CASH,
            current_value=Money.from_val(15000.0),
        ),
    ]

    liabilities = [
        Liability(
            id="l1",
            name="Mortgage",
            loan_type=LoanType.MORTGAGE,
            principal_balance=Money.from_val(60000.0),
            interest_rate_pct=Decimal("2.1"),
            monthly_payment=Money.from_val(650.0),
        )
    ]

    cashflow = MonthlyCashflow(
        monthly_income=Money.from_val(4800.0),
        fixed_costs=Money.from_val(1500.0),
        debt_payments=Money.from_val(650.0),
        living_expenses=Money.from_val(1200.0),
    )

    bs = BalanceSheet(assets=assets, liabilities=liabilities, cashflow=cashflow)

    assert bs.total_assets.amount == Decimal("107500.00")
    assert bs.total_liabilities.amount == Decimal("60000.00")
    assert bs.net_worth.amount == Decimal("47500.00")
    assert bs.free_monthly_cashflow.amount == Decimal("1450.00")  # 4800 - (1500 + 650 + 1200)
