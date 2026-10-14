# Wealth Pilot 🧭

> **Strategic Wealth & Asset Allocation Guidance Platform**

Wealth Pilot is an asynchronous, open-source personal financial planning platform designed for mid-to-long term wealth management. It bridges real-world investment portfolios (PDT, brokers) and bank account cashflow (KBC, Bunq, generic CSV) to deliver proactive guidance on asset allocation buckets, debt repayment strategy, and compound net worth trajectories.

---

## Features

- **Dynamic Asset Allocation Buckets**: Define custom buckets (Core ETF, Tech/Growth, Physical Gold, Emergency Buffer, Real Estate) with drift tolerances and asset-to-bucket mappings.
- **Multi-Source Data Ingestion**:
  - **PDT MCP Client**: Real-time look-through of holdings, ETF X-Ray, prices, and dividends.
  - **KBC Bank CSV**: Automated extraction of liquid cash balance, mortgage payments (`Woningkrediet`), consumer debt, recurring expenses, and net savings rate.
  - **Generic CSV/Excel & YAML**: Flexible balance sheet modeling for accounts, debts, and properties.
- **Strategic Advice Engine**:
  - **Smart Monthly Cash Injection**: Direct incoming savings to underweight buckets without triggering forced sales, fees, or taxes.
  - **Debt Payoff vs. Investing Advisor**: Avalanche vs Snowball vs Expected Portfolio Return comparison.
  - **Belgian Tax Optimization**: Reference-date fiscal cost basis (Dec 31, 2025), annual €10k capital gains exemption tracking, FIFO lot management.
  - **Net Worth Milestone Projections**: Compound growth trajectories over 5, 10, 20, and 30 years.
- **Dual Delivery Interface**:
  - **Textual TUI**: Keyboard-first interactive terminal dashboard (`wealth-pilot tui`).
  - **FastAPI Web Dashboard**: Browser-based local dashboard with file upload and interactive charts (`wealth-pilot web`).
  - **Scriptable CLI**: Direct terminal reporting (`wealth-pilot status`, `wealth-pilot advise`).

---

## Installation & Quick Start

Requires Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/your-org/wealth-pilot.git
cd wealth-pilot

# Install dependencies with uv
uv sync

# Run the Terminal UI
uv run wealth-pilot tui

# Run the Local Web Dashboard
uv run wealth-pilot web

# Run CLI Status Report
uv run wealth-pilot status
```

---

## Architecture

Wealth Pilot strictly adheres to **Uncle Bob's Clean Architecture**:

- `domain/`: Pure business models (`Money`, `Asset`, `Liability`, `Bucket`, `AllocationRule`, `BalanceSheet`). Zero third-party dependencies.
- `use_cases/`: Application business rules (`CalculateBucketAllocation`, `AdviseContribution`, `AdviseDebtPayoff`, `ProjectNetWorth`, `OptimizeTax`).
- `adapters/`: Ingestion gateways (PDT MCP, KBC CSV, Generic CSV/YAML) and repositories.
- `delivery/`: Textual TUI (`delivery/tui`), FastAPI Web Dashboard (`delivery/web`), and CLI (`cli.py`).

---

## License

MIT License.
