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

To model primary residence equity alongside mortgages:

```yaml
manual_assets:
  - id: "primary-home"
    name: "Primary Residence (Estimated Market Value)"
    asset_class: "REAL_ESTATE"
    current_value: 420000.00
    institution: "Private Property"

manual_liabilities:
  - id: "mortgage-woningkrediet-1"
    name: "KBC Woningkrediet (Fixed Rate)"
    loan_type: "MORTGAGE"
    principal_balance: 140000.00
    interest_rate_pct: 1.85
    monthly_payment: 579.68
    institution: "KBC"
```
