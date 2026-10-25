# Wealth Pilot Documentation 🧭

> **Strategic Wealth & Asset Allocation Guidance Platform**

Welcome to the documentation for **Wealth Pilot**, an open-source, local-first platform designed for mid-to-long term wealth planning, strategic asset allocation, and actionable financial guidance.

---

## Why Wealth Pilot?

Most personal finance apps fall into one of two extremes:
1. **Micro-Budgeting Apps** (e.g. YNAB, Monarch): Focus on categorizing small daily expenses and managing envelope budgets. They offer little to no strategic investment guidance.
2. **Passive Net Worth Dashboards** (e.g. Kubera, Finary): Provide high-level aggregation across accounts, but lack proactive advice on how to rebalance, which debts to pay off, or where to deploy monthly surplus cashflow.

**Wealth Pilot bridges this gap**:
- **Macro Allocation Buckets**: Organize assets into target pillars (e.g. Core World ETFs, High-Conviction Growth, Gold/Commodities, Cash Buffers, Real Estate) with customizable drift tolerances.
- **Unified Balance Sheet**: Connects investment accounts (PDT MCP), bank checking cashflow (KBC CSV), savings accounts (Bunq), and active debts (mortgages, credit lines).
- **Proactive Guidance Engine**: Rebalances portfolios using incoming monthly cash deposits (**Buy-Only Rebalancing**) without forcing taxable asset sales or broker fees.
- **Belgian 2026 Capital Gains Tax Optimizer**: FIFO lot tracking with Dec 31, 2025 benchmark price lookup and €10,000 annual exemption optimization.
- **Debt vs. Investing Optimization**: Evaluates debt APR against long-term expected portfolio returns (Avalanche vs Snowball).
- **Server-Side AI Advisor**: Pluggable LLM interface (BYO API key) delivering personalized strategic commentary with zero client-side credential exposure.
- **Privacy & Security First**: Envelope encryption (`SecretVault` with AES-256-GCM), local SQLite database, and network bind guards.
- **Containerized & Mobile-Ready**: Run locally or via Docker Compose with **Tailscale**, **Cloudflare Tunnel**, or **DuckDNS + Caddy** for secure remote phone access.

---

## Architectural Highlights

Wealth Pilot strictly implements **Uncle Bob's Clean Architecture**:

- `domain/`: Pure business models (`Money`, `Asset`, `Liability`, `Bucket`, `AllocationRule`, `BalanceSheet`, `User`, `TenantContext`). Zero third-party dependencies.
- `use_cases/`: Application business rules (`CalculateBucketAllocation`, `AdviseContribution`, `AdviseDebtPayoff`, `ProjectNetWorth`, `CategorizeTransactions`, `OptimizeTax`, `BuildPortfolioOverview`).
- `adapters/`: Ingestion gateways (KBC CSV, PDT MCP, Generic CSV), repositories (`ConfigRepository`, `LocalDbRepository`), security (`SecretVault`), and settings (`AppSettings`).
- `delivery/`: Modern local FastAPI web dashboard (`delivery/web`) with PWA and mobile bottom navigation, authentication manager (`AuthManager`), and scriptable CLI (`cli.py`).
