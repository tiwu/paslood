"""Unit tests for Wealth Pilot Use Cases (Layer 2 - Application Business Rules)."""

from decimal import Decimal

from wealth_pilot.domain.asset import Asset, AssetClass
from wealth_pilot.domain.bucket import AllocationRule, Bucket, DriftStatus
from wealth_pilot.domain.liability import Liability, LoanType
from wealth_pilot.domain.money import Money
from wealth_pilot.use_cases.advise_contribution import AdviseContributionUseCase
from wealth_pilot.use_cases.advise_debt_payoff import AdviseDebtPayoffUseCase
from wealth_pilot.use_cases.calculate_allocation import CalculateBucketAllocationUseCase
from wealth_pilot.use_cases.categorize_transactions import CategorizeTransactionsUseCase
from wealth_pilot.use_cases.optimize_tax import OptimizeTaxUseCase
from wealth_pilot.use_cases.project_net_worth import ProjectNetWorthUseCase


def test_calculate_bucket_allocation_and_drift():
    assets = [
        Asset(id="1", name="ASML", symbol="ASML", current_value=Money.from_val(60000.0)),
        Asset(
            id="2",
            name="VWCE",
            symbol="VWCE",
            asset_class=AssetClass.ETF,
            current_value=Money.from_val(30000.0),
        ),
        Asset(
            id="3",
            name="Physical Gold",
            symbol="GOLD",
            asset_class=AssetClass.COMMODITY,
            current_value=Money.from_val(10000.0),
        ),
    ]

    buckets = [
        Bucket(
            id="b_tech",
            name="Tech / ASML",
            target_weight_pct=Decimal("40.0"),
            drift_tolerance_pct=Decimal("3.0"),
            rules=[AllocationRule(symbols={"ASML"})],
        ),
        Bucket(
            id="b_etf",
            name="World ETFs",
            target_weight_pct=Decimal("50.0"),
            drift_tolerance_pct=Decimal("3.0"),
            rules=[AllocationRule(asset_classes={AssetClass.ETF})],
        ),
        Bucket(
            id="b_gold",
            name="Gold",
            target_weight_pct=Decimal("10.0"),
            drift_tolerance_pct=Decimal("2.0"),
            rules=[AllocationRule(symbols={"GOLD"})],
        ),
    ]

    use_case = CalculateBucketAllocationUseCase()
    results = use_case.execute(assets=assets, buckets=buckets)

    assert len(results) == 3

    tech = next(r for r in results if r.bucket_id == "b_tech")
    etf = next(r for r in results if r.bucket_id == "b_etf")
    gold = next(r for r in results if r.bucket_id == "b_gold")

    assert tech.current_weight_pct == Decimal("60.00")
    assert tech.target_weight_pct == Decimal("40.00")
    assert tech.drift_status == DriftStatus.OVERWEIGHT
    assert tech.diff_value == Decimal("20000.00")

    assert etf.current_weight_pct == Decimal("30.00")
    assert etf.target_weight_pct == Decimal("50.00")
    assert etf.drift_status == DriftStatus.UNDERWEIGHT
    assert etf.diff_value == Decimal("-20000.00")

    assert gold.current_weight_pct == Decimal("10.00")
    assert gold.drift_status == DriftStatus.BALANCED


def test_advise_contribution_buy_only():
    assets = [
        Asset(id="1", name="ASML", symbol="ASML", current_value=Money.from_val(60000.0)),
        Asset(
            id="2",
            name="VWCE",
            symbol="VWCE",
            asset_class=AssetClass.ETF,
            current_value=Money.from_val(30000.0),
        ),
        Asset(
            id="3",
            name="Physical Gold",
            symbol="GOLD",
            asset_class=AssetClass.COMMODITY,
            current_value=Money.from_val(10000.0),
        ),
    ]

    buckets = [
        Bucket(
            id="b_tech",
            name="Tech",
            target_weight_pct=Decimal("40.0"),
            rules=[AllocationRule(symbols={"ASML"})],
        ),
        Bucket(
            id="b_etf",
            name="World ETF",
            target_weight_pct=Decimal("50.0"),
            rules=[AllocationRule(symbols={"VWCE"})],
        ),
        Bucket(
            id="b_gold",
            name="Gold",
            target_weight_pct=Decimal("10.0"),
            rules=[AllocationRule(symbols={"GOLD"})],
        ),
    ]

    alloc_calc = CalculateBucketAllocationUseCase()
    alloc_results = alloc_calc.execute(assets=assets, buckets=buckets)

    advise_use_case = AdviseContributionUseCase()
    # User has €2,000 monthly surplus to invest
    plan = advise_use_case.execute(deposit=Money.from_val(2000.0), allocation_results=alloc_results)

    # ETF is the only underweight bucket (needs €20k), so 100% of €2,000 should go to ETF!
    assert len(plan) == 1
    assert plan[0].bucket_id == "b_etf"
    assert plan[0].amount.amount == Decimal("2000.00")


def test_advise_debt_payoff_avalanche_vs_investing():
    liabilities = [
        Liability(
            id="mortgage",
            name="Home Mortgage",
            loan_type=LoanType.MORTGAGE,
            principal_balance=Money.from_val(200000.0),
            interest_rate_pct=Decimal("1.85"),
            monthly_payment=Money.from_val(850.0),
        ),
        Liability(
            id="credit",
            name="Consumer Line",
            loan_type=LoanType.CONSUMER_LOAN,
            principal_balance=Money.from_val(4000.0),
            interest_rate_pct=Decimal("9.50"),
            monthly_payment=Money.from_val(250.0),
        ),
    ]

    use_case = AdviseDebtPayoffUseCase()
    advices = use_case.execute(
        liabilities=liabilities,
        monthly_surplus=Money.from_val(1000.0),
        expected_portfolio_return_pct=Decimal("7.0"),
    )

    # Should prioritize consumer line with 9.50% APR above mortgage and investment hurdle!
    assert len(advices) >= 1
    top_advice = advices[0]
    assert "Consumer Line" in top_advice.title or "9.50%" in top_advice.message
    assert top_advice.priority.value in ("CRITICAL", "HIGH")


def test_project_net_worth_compounding():
    use_case = ProjectNetWorthUseCase()
    trajectory = use_case.execute(
        initial_assets=Money.from_val(100000.0),
        initial_debts=Money.from_val(50000.0),
        monthly_savings=Money.from_val(1500.0),
        annual_return_pct=Decimal("7.0"),
        years=10,
    )

    assert len(trajectory) == 11  # Year 0 to 10
    assert trajectory[0]["year"] == 0
    assert trajectory[0]["net_worth"] == Decimal("50000.00")
    assert trajectory[10]["year"] == 10
    # Compounded net worth over 10 years must be substantially higher
    assert trajectory[10]["net_worth"] > Decimal("400000.00")


def test_categorize_transactions_and_rule_learning():
    from wealth_pilot.domain.balance_sheet import Transaction

    txs = [
        Transaction(
            id="tx1",
            date="2026-05-01",
            amount=Money.from_val(-579.68),
            account_id="kbc",
            description="TERUGBETALING WONINGKREDIET REFERENTIE 420-3625993-43",
        ),
        Transaction(
            id="tx2",
            date="2026-05-02",
            amount=Money.from_val(-45.50),
            account_id="kbc",
            description="ALDI SUPERMARKT",
            counterparty_name="ALDI 51",
        ),
    ]

    use_case = CategorizeTransactionsUseCase()
    categorized = use_case.execute(transactions=txs, rules=[])

    assert categorized[0].category == "MORTGAGE"
    assert categorized[1].category == "GROCERIES"

    # Now simulate user re-bucketing tx2 to 'HOME_EXPENSE' and saving rule
    new_rule = use_case.create_rule(
        match_field="counterparty_name",
        pattern="ALDI",
        target_category="HOME_EXPENSE",
    )
    re_categorized = use_case.execute(transactions=[txs[1]], rules=[new_rule])
    assert re_categorized[0].category == "HOME_EXPENSE"


def test_belgian_tax_optimization():
    use_case = OptimizeTaxUseCase()
    res = use_case.calculate_asml_tax(
        shares_to_sell=Decimal("10.0"),
        current_price=Money.from_val(1597.0),
        peildatum_price=Money.from_val(912.0),
        available_annual_exemption=Money.from_val(10000.0),
    )

    # Gain per share = 1597 - 912 = 685. Total gain = 6850.
    # Exemption = 10000. Tax = 0.
    assert res["taxable_gain"].amount == Decimal("6850.00")
    assert res["tax_to_pay"].amount == Decimal("0.00")
    assert res["remaining_exemption"].amount == Decimal("3150.00")
