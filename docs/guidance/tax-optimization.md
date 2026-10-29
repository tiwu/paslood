# Belgian Fiscal Shield & Employee Equity Tax Optimization

Paslood implements an automated Belgian tax engine for investors holding global ETFs alongside corporate employee share schemes at foreign custodians (e.g., corporate equity plans administered by **EquatePlus / Equatex AG Zurich**).

---

## 1. Statutory Legal Sources (FOD Financiën)

All rates, thresholds, and valuation rules in `tax_rules.py` and `optimize_tax.py` strictly adhere to Belgian fiscal law:

| Regime | Legal Citation | Key Provisions |
| :--- | :--- | :--- |
| **2026 Meerwaardebelasting** | *WIB 92 Art. 90, 1°, 9° & Art. 101–102* | 10% tax on net realized gains; 31 Dec 2025 fotomoment cost basis; €10,000 base exemption with 5-year carryover. |
| **Taks op de beursverrichtingen (TOB)** | *WDRT Art. 120–126/2* | 0.12%, 0.35%, and 1.32% transaction taxes with statutory transaction caps. |
| **Reynderstaks** | *WIB 92 Art. 19bis* | 30% withholding tax on the fixed-income yield of funds holding $>10\%$ debt claims. |

---

## 2. Belgian Fiscal Shield Calculation Pipeline

```mermaid
flowchart TD
    START[Sale of Asset / Shares] --> DATE{Acquisition Date?}
    DATE -->|On or Before 31 Dec 2025| BENCH["Default Benchmark Cost Basis:<br/>Official Dec 31, 2025 Closing Price"]
    DATE -->|After 31 Dec 2025| HIST["Cost Basis:<br/>Actual Historical Purchase Price"]

    BENCH --> PROT{Historical Purchase Price > Dec 31 2025 Price?}
    PROT -->|Yes| MAX["Historical Loss Protection Rule:<br/>Use max(Dec 31 2025, Historical Buy Price)"]
    PROT -->|No| BASE["Use Dec 31 2025 Closing Price"]

    HIST --> TAXABLE
    MAX --> TAXABLE
    BASE --> TAXABLE

    TAXABLE["Calculate Fiscal Capital Gain:<br/>Proceeds - Cost Basis - Allowable Fees"]
    TAXABLE --> EXEMPT{"Apply Annual CGT Exemption<br/>€10,000 base + carryover (max €15,000)"}

    EXEMPT -->|Gain &le; Exemption| ZERO_TAX["Belgian CGT: €0.00"]
    EXEMPT -->|Gain > Exemption| NET_TAX["Taxable Net Gain = Gain - Exemption<br/>Belgian CGT: 10.0%"]

    START --> BROKER{"Custodian Profile?"}
    BROKER -->|Belgian Broker| BE_BROKER["Broker withholds Belgian TOB automatically"]
    BROKER -->|Foreign Custodian (EquatePlus)| CH_BROKER["Foreign Deductions Reconciled:<br/>- 0.35% Broker Commission<br/>- 0.15% Swiss Stamp Duty (Zegelrechten)<br/>- Alert: 0.35% Belgian TOB Self-Declaration (M+2)"]

    START --> REYNDERS{Asset holds >10% debt claims?}
    REYNDERS -->|Yes| REYN_TAX["Reynders Tax (WIB 92 Art. 19bis):<br/>30.0% withholding on fixed-income yield"]
    REYNDERS -->|No| REYN_NO["No Reynders Tax"]
```

---

## 3. Statutory TOB Tiers (`WDRT Art. 120`)

| Tier | Rate | Transaction Plafond | Applicable Instrument Types |
| :--- | :--- | :--- | :--- |
| **Low** | **0.12%** | **€ 1,300.00** | EEA distributing ETFs, government & corporate bonds, Belgian REITs (*GVV/SIR*). |
| **Medium** | **0.35%** | **€ 1,600.00** | Individual equities (single stocks), non-EEA ETFs, Gold/Commodity ETCs. |
| **High** | **1.32%** | **€ 4,000.00** | Accumulating funds and ETFs registered in Belgium. |

---

## 4. Foreign Custodian (EquatePlus) Reconciliation

When selling shares through Swiss or foreign custodians, settlement statements contain non-Belgian levies that distort net proceeds:

1. **`Provisies` (`0.35%`)**: Foreign custodian brokerage commission (not Belgian TOB).
2. **`Zegelrechten bij verkoop` (`0.15%`)**: Swiss Federal Securities Transfer Stamp Duty (*Umsatzabgabe*).
3. **Unwithheld Belgian TOB (`0.35%`)**: Because foreign custodians do not withhold Belgian TOB, the investor must file a self-declaration and pay TOB to FOD Financiën by the **last business day of the second month** following the transaction (`M+2`).
4. **Fotomoment Gain vs. Statement FMV**: Foreign statements report capital gains relative to initial grant fair market value (FMV). Paslood calculates the legal Belgian fiscal gain against the 31 Dec 2025 benchmark price, preventing overpayment of taxes.
