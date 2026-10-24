"""Extended unit tests for Domain Entities & Edge Cases."""

from decimal import Decimal

from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.balance_sheet import BalanceSheet, MonthlyCashflow, Transaction
from wealth_pilot.domain.bucket import AllocationRule, Bucket
from wealth_pilot.domain.liability import Liability, LoanType
from wealth_pilot.domain.money import Money


def test_money_comparisons_and_operators():
    m1 = Money(Decimal("100.00"), "EUR")
    m2 = Money(Decimal("200.00"), "EUR")
    m3 = Money(Decimal("100.00"), "EUR")

    assert m1 < m2
    assert m1 <= m2
    assert m1 <= m3
    assert m2 > m1
    assert m2 >= m1
    assert m1 >= m3
    assert m1 == m3
    assert m1 != m2
    assert m1 != "not-money"
    assert m1 != 100


def test_money_division_and_multiplication():
    m = Money(Decimal("150.00"), "EUR")
    assert (m / 2).amount == Decimal("75.00")
    assert (m / Decimal("3.0")).amount == Decimal("50.00")
    # Division by zero should return 0 safely
    assert (m / 0).amount == Decimal("0.00")
    assert (m * 2).amount == Decimal("300.00")
    assert (m * 0.5).amount == Decimal("75.00")


def test_money_formatting_and_currencies():
    m_eur = Money(Decimal("1234567.89"), "EUR")
    assert m_eur.format() == "€ 1.234.567,89"
    assert m_eur.format(show_symbol=False) == "1.234.567,89"
    assert m_eur.format(decimals=0) == "€ 1.234.568"

    m_usd = Money(Decimal("5000.50"), "USD")
    assert m_usd.format() == "$ 5.000,50"

    m_gbp = Money(Decimal("250.00"), "GBP")
    assert "GBP" in m_gbp.format()

    m_neg = Money(Decimal("-450.00"), "EUR")
    assert m_neg.format() == "€ -450,00"
    assert repr(m_neg) == "Money(-450.00, 'EUR')"


def test_money_from_val_and_parsing_edge_cases():
    assert Money.from_val(None).amount == Decimal("0.00")
    assert Money.from_val(Money(10)).amount == Decimal("10.00")
    assert Money.from_val({"value": 250.5, "currency": "USD"}).currency == "USD"
    assert Money.from_val({"amount": 100.0}).amount == Decimal("100.00")
    assert Money("   $ 1.500,25 ").amount == Decimal("1500.25")
    # Invalid string fallback
    assert Money("invalid_string_amount").amount == Decimal("0.00")
    assert Money(["invalid", "type"]).amount == Decimal("0.00")


def test_asset_edge_cases():
    # Asset with zero quantity
    a_zero_qty = Asset(
        id="a1",
        name="Zero Shares",
        quantity=Decimal("0.0"),
        current_value=Money.from_val(500.0),
    )
    assert a_zero_qty.unit_price == Money.from_val(500.0)
    assert a_zero_qty.unrealized_gain.amount == Decimal("0.00")
    assert a_zero_qty.unrealized_gain_pct == Decimal("0.00")

    # Asset with cost basis
    a_with_basis = Asset(
        id="a2",
        name="Profitable Stock",
        quantity=Decimal("10.0"),
        current_value=Money.from_val(1500.0),
        cost_basis=Money.from_val(1000.0),
    )
    assert a_with_basis.unit_price.amount == Decimal("150.00")
    assert a_with_basis.unrealized_gain.amount == Decimal("500.00")
    assert a_with_basis.unrealized_gain_pct == Decimal("50.00")


def test_allocation_rule_matching_variations():
    rule_isin = AllocationRule(isins={"US0378331005"})
    rule_ac = AllocationRule(asset_classes={AssetClass.COMMODITY})
    rule_inst = AllocationRule(institutions={"DEGIRO"})
    rule_kw = AllocationRule(name_keywords={"Vanguard", "All-World"})

    a_apple = Asset(id="1", name="Apple Inc", isin="US0378331005")
    a_gold = Asset(id="2", name="Gold ETC", asset_class=AssetClass.COMMODITY)
    a_broker = Asset(id="3", name="Some Stock", institution="DEGIRO")
    a_etf = Asset(id="4", name="Vanguard FTSE All-World UCITS")

    assert rule_isin.matches(a_apple)
    assert rule_ac.matches(a_gold)
    assert rule_inst.matches(a_broker)
    assert rule_kw.matches(a_etf)

    # Empty rules
    empty_bucket = Bucket(id="b_empty", name="Empty", rules=[])
    assert not empty_bucket.matches(a_apple)
    assert empty_bucket.target_weight == Decimal("0.0")


def test_liability_and_debt_metrics():
    debt = Liability(
        id="l1",
        name="Personal Loan",
        loan_type=LoanType.CONSUMER_LOAN,
        principal_balance=Money.from_val(12000.0),
        interest_rate_pct=Decimal("6.0"),
        monthly_payment=Money.from_val(350.0),
    )
    assert debt.annual_interest_cost.amount == Decimal("720.00")
    assert debt.is_high_interest(threshold_pct=Decimal("5.0")) is True
    assert debt.is_high_interest(threshold_pct=Decimal("7.0")) is False


def test_liability_amortization_and_percentage_payments():
    # 1. Percentage-based monthly payment (e.g. Credit Card / Flex Budget Loan)
    flex_loan = Liability(
        id="flex1",
        name="KBC Flex Budget",
        loan_type=LoanType.CREDIT_CARD,
        principal_balance=Money.from_val(5000.0),
        interest_rate_pct=Decimal("10.0"),
        monthly_payment_pct=Decimal("5.0"),  # 5% of €5000 = €250/mo
    )
    assert flex_loan.effective_monthly_payment.amount == Decimal("250.00")

    # 2. Auto-estimated remaining balance and payment from start capital, start date, and duration
    # Start 10 years (120 months) ago out of 20 years (240 months) at 2.0% APR on €200,000
    est_bal, est_pmt = Liability.calculate_amortized_state(
        start_capital=Money.from_val(200000.0),
        interest_rate_pct=Decimal("2.0"),
        start_date="2016-10-01",
        duration_months=240,
        as_of_date="2026-10-01",
    )
    # Monthly payment on €200k @ 2% for 240m is ~€1,011.77
    assert Decimal("1005.00") <= est_pmt.amount <= Decimal("1020.00")
    # Halfway through a 2% loan, remaining principal is slightly over 50% (~€110k)
    assert Decimal("105000.00") <= est_bal.amount <= Decimal("115000.00")

    # Zero-interest loan linear amortization halfway through
    est_bal_zero, est_pmt_zero = Liability.calculate_amortized_state(
        start_capital=Money.from_val(12000.0),
        interest_rate_pct=Decimal("0.0"),
        start_date="2025-10-01",
        end_date="2027-10-01",
        as_of_date="2026-10-01",
    )
    assert est_pmt_zero.amount == Decimal("500.00")
    assert est_bal_zero.amount == Decimal("6000.00")


def test_balance_sheet_edge_cases():
    # Empty balance sheet
    bs_empty = BalanceSheet(assets=[], liabilities=[])
    assert bs_empty.total_assets.amount == Decimal("0.00")
    assert bs_empty.total_liabilities.amount == Decimal("0.00")
    assert bs_empty.net_worth.amount == Decimal("0.00")
    assert bs_empty.debt_to_asset_ratio == Decimal("0.00")

    # Zero income cashflow savings rate
    cf_zero_inc = MonthlyCashflow(
        monthly_income=Money.from_val(0.0),
        living_expenses=Money.from_val(500.0),
    )
    bs_zero_inc = BalanceSheet(assets=[], liabilities=[], cashflow=cf_zero_inc)
    assert bs_zero_inc.cashflow.savings_rate_pct == Decimal("0.00")
    assert bs_zero_inc.free_monthly_cashflow.amount == Decimal("-500.00")


def test_transaction_entity():
    tx = Transaction(
        id="tx1",
        date="2026-10-01",
        amount=Money.from_val(-45.50),
        account_id="acc1",
        description="DELHAIZE SUPERMARKET",
        counterparty_name="DELHAIZE",
        category="GROCERIES",
    )
    assert tx.is_outflow is True
    assert tx.is_inflow is False

    tx_inc = Transaction(
        id="tx2",
        date="2026-10-02",
        amount=Money.from_val(2500.0),
        account_id="acc1",
        description="SALARY",
        category="INCOME",
    )
    assert tx_inc.is_inflow is True
    assert tx_inc.is_outflow is False
