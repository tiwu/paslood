# Manual Accounts & Bunq Integration

Certain financial assets and liabilities don't require automated feeds or CSV statements to track accurately. Paslood allows you to define these directly in your `portfolio.yaml` or through the Web UI.

---

## Configuring Bunq Savings

For accounts like **Bunq High-Yield Savings** where you maintain an emergency reserve:

```yaml
manual_assets:
  - id: "bunq-savings"
    name: "Bunq High-Yield Savings"
    symbol: "SAVINGS"
    asset_class: "CASH"
    current_value: 15000.00
    institution: "Bunq"
    currency: "EUR"
```

---

## Configuring Real Estate & Mortgages

To model primary residence equity alongside mortgages, provide valuation, cost basis, and loan schedule parameters:

```yaml
manual_assets:
  - id: "primary-home"
    name: "Primary Residence"
    asset_class: "REAL_ESTATE"
    current_value: 450000.00
    cost_basis: 320000.00
    acquisition_date: "2019-06-15"
    institution: "Private Property"

manual_liabilities:
  - id: "mortgage-woningkrediet-1"
    name: "KBC Woningkrediet (Fixed Rate)"
    loan_type: "MORTGAGE"
    start_capital: 250000.00
    principal_balance: 140000.00
    interest_rate_pct: 1.85
    monthly_payment: 579.68
    start_date: "2019-06-01"
    duration_months: 240
    institution: "KBC"
```

### Key Fields for Wealth Projections

- **`acquisition_date` & `cost_basis`**: Used by the projection engine to determine portfolio inception date and compute historical cost benchmarks (e.g. Belgian capital gains tax relief thresholds).
- **`start_capital`, `start_date`, and `duration_months`**: Enables automatic principal balance estimation and amortization modeling when remaining balances change over time.
