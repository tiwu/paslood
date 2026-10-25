# Paslood (Wealth Pilot) Documentation 🧭

> **Whole-Life Balance Sheet, PDT Strategic Companion & Belgian Fiscal Shield**
>
> *"You can't know where you're going if you don't know where you are."*

Welcome to the documentation for **Paslood** (*in het lood staan* — plumb-line alignment for your personal balance sheet), an open-source, local-first platform designed to unify your brokerage portfolio with your real-world off-broker assets, debts, and Belgian fiscal obligations.

---

## Why Paslood?

Brokerage portfolio trackers like **Portfolio Dividend Tracker (PDT)** do the heavy lifting of importing broker CSVs (e.g., Saxo) and tracking dividend income. However, **PDT only sees your brokerage accounts**. It knows nothing about:

- **Checking & Savings Accounts**: Cash buffers at KBC or Bunq.
- **Pillar Pensions**: KBC pension savings (*pensioensparen*).
- **Real Estate & Loans**: Primary residence value, mortgage principal/APR, or consumer/vehicle loans (e.g., Alpha Credit motorcycle loan).
- **Employee Stock Concentration & Foreign Custodians**: Recurring employee share purchase plans (e.g., 0–10% gross salary quarterly ASML stock purchases + lump-sum grants on **EquatePlus / Equatex AG Zurich**) and the Belgian tax traps hidden on foreign settlement PDFs.

**Paslood bridges this gap as your Strategic Decision Engine**:
- **Macro Allocation Buckets**: Organize your *entire* financial life into target pillars (Core World ETFs, Employee Stock / High-Conviction Growth, Gold/Commodities, Cash Buffers, Real Estate) with customizable drift tolerances.
- **Buy-Only Rebalancing**: Directs incoming monthly savings to underweight buckets without forcing taxable sales.
- **Legally Grounded Belgian Fiscal Shield**:
  - **2026 Meerwaardebelasting (`WIB 92 Art. 90/101`)**: Uses `max(31 Dec 2025 Fotomoment, Historical Purchase Price)` as legal cost basis, models the `€10,000` annual exemption (`+€1,000/yr` 5-year carryover, doubled for joint filing), and solves the exact **Max Tax-Free Share Trim** to de-concentrate employee stock at `€0.00` CGT.
  - **EquatePlus (Zurich) Reconciliation & TOB (`WDRT Art. 120-126/2`)**: Separates Equatex AG's `0.35%` commission and `0.15%` Swiss stamp duty (*Zegelrechten*) from unwithheld **Belgian TOB (`0.35%`)**, alerting you to the bi-monthly FOD Financiën declaration deadline.
  - **Reynders Tax (`WIB 92 Art. 19bis`)**: Computes the `30%` withholding tax on fixed-income/money-market funds (`>10%` debt claims).
- **Debt vs. Investing Optimization**: Evaluates loan APRs (mortgage, vehicle loan) against long-term expected portfolio CAGR.
- **Server-Side AI Advisor & Privacy First**: Envelope encryption (`SecretVault` with AES-256-GCM), local SQLite database, and Tailscale / Cloudflare Tunnel mobile access.

---

## Architectural Highlights

Paslood strictly implements **Clean Architecture**:

- `domain/`: Pure business models (`Money`, `Asset`, `Liability`, `Bucket`, `AllocationRule`, `BalanceSheet`, `TobTier`, `BrokerTaxProfile`, `BelgianTaxCitation`). Zero third-party dependencies.
- `use_cases/`: Application business rules (`CalculateBucketAllocation`, `AdviseContribution`, `AdviseDebtPayoff`, `ProjectNetWorth`, `CategorizeTransactions`, `OptimizeTax`, `BuildPortfolioOverview`).
- `adapters/`: Ingestion gateways (KBC CSV, PDT MCP, Generic CSV), repositories (`ConfigRepository`, `LocalDbRepository`), security (`SecretVault`), and settings (`AppSettings`).
- `delivery/`: Modern local FastAPI web dashboard (`delivery/web`) with PWA and mobile bottom navigation, authentication manager (`AuthManager`), and scriptable CLI (`cli.py`).
