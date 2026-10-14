# Wealth Pilot Documentation 🧭

> **Strategic Wealth & Asset Allocation Guidance Platform**

Welcome to the documentation for **Wealth Pilot**, an open-source, local-first platform designed for mid-to-long term wealth planning, strategic asset allocation, and actionable financial guidance.

---

## Why Wealth Pilot?

Most personal finance apps fall into one of two extremes:
1. **Micro-Budgeting Apps** (e.g. YNAB, Monarch): Focus on categorizing every €3 coffee and managing envelope budgets. They offer little to no strategic investment guidance.
2. **Passive Net Worth Dashboards** (e.g. Kubera, Finary): Provide high-level aggregation across accounts, but lack proactive advice on how to rebalance, which debts to pay off, or where to deploy monthly surplus cashflow.

**Wealth Pilot bridges this gap**:
- **Macro Allocation Buckets**: Organize assets into target pillars (e.g. Core World ETFs, High-Conviction Growth, Gold/Commodities, Cash Buffers, Real Estate) with customizable drift tolerances.
- **Unified Balance Sheet**: Connects investment accounts (PDT MCP), bank checking cashflow (KBC CSV), savings accounts (Bunq), and active debts (mortgages, credit lines).
- **Proactive Guidance Engine**: Rebalances portfolios using incoming monthly cash deposits (**Buy-Only Rebalancing**) without forcing taxable asset sales or broker fees.
- **Debt vs. Investing Optimization**: Evaluates debt APR against long-term expected portfolio returns (Avalanche vs Snowball).
- **AI Financial Advisor**: Pluggable LLM interface (BYO API key) delivering personalized strategic commentary.
- **Privacy & Zero Vendor Lock-in**: 100% local execution with zero cloud telemetry.

---

## Architectural Highlights

Wealth Pilot strictly implements **Uncle Bob's Clean Architecture**:

- `domain/`: Pure business models (`Money`, `Asset`, `Liability`, `Bucket`, `AllocationRule`, `BalanceSheet`). Zero third-party dependencies.
- `use_cases/`: Application business rules (`CalculateBucketAllocation`, `AdviseContribution`, `AdviseDebtPayoff`, `ProjectNetWorth`, `CategorizeTransactions`, `OptimizeTax`).
- `adapters/`: Ingestion gateways (KBC CSV, PDT MCP, Generic CSV/YAML) and repositories.
- `delivery/`: Modern local FastAPI web dashboard with PWA support, alongside a scriptable CLI.
