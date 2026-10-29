# Manual Accounts & Asset Configuration

Assets and debts that do not require recurring statement uploads (e.g. real estate appraisals, fixed mortgage amortization schedules, high-yield cash reserves) can be configured directly in `portfolio.yaml` or through the Web UI.

---

## Configuration Schema

### 1. Manual Cash & Savings Assets

```yaml
manual_assets:
  - id: "bunq-savings"
    name: "High-Yield Savings Reserve"
    symbol: "SAVINGS"
    asset_class: "CASH"
    current_value: 15000.00
    institution: "Bunq"
    currency: "EUR"
```

---

### 2. Real Estate & Mortgage Amortization

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
    name: "Fixed-Rate Home Mortgage"
    loan_type: "MORTGAGE"
    start_capital: 250000.00
    principal_balance: 140000.00
    interest_rate_pct: 1.85
    monthly_payment: 579.68
    start_date: "2019-06-01"
    duration_months: 240
    institution: "KBC"
```

---

## Field Reference

| Field | Applicable Aggregate | Purpose |
| :--- | :--- | :--- |
| `cost_basis` | `Asset` | Benchmark acquisition cost used in capital gains tax relief calculations. |
| `acquisition_date` | `Asset` | Establishes portfolio inception and determines pre-2026 tax status. |
| `interest_rate_pct` | `Liability` | Annual Percentage Rate (APR) evaluated against expected portfolio CAGR. |
| `monthly_payment` | `Liability` | Fixed monthly debt servicing deducted from gross income to compute free cashflow. |
| `duration_months` | `Liability` | Total amortization period used to calculate remaining balance trajectories. |
