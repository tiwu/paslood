# Getting Started with Wealth Pilot

Follow this guide to get Wealth Pilot running locally in minutes.

---

## Prerequisites

- **Python 3.10+**
- [`uv`](https://docs.astral.sh/uv/) (Modern high-performance Python package manager)

```bash
# Install uv if you don't already have it
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/tiwu/wealth-pilot.git
cd wealth-pilot

# Sync dependencies into local virtual environment
uv sync --extra dev
```

---

## Launching the Application

### 1. Interactive Web Dashboard (Recommended)

Launch the local web dashboard:

```bash
uv run wealth-pilot web
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

- **Mobile / PWA**: On iOS (Safari) or Android (Chrome), tap **Share** -> **Add to Home Screen** to install Wealth Pilot as a standalone mobile application.

### 2. Scriptable CLI Commands

Wealth Pilot includes a rich terminal CLI for quick checks:

```bash
# View consolidated Balance Sheet, Net Worth, and Bucket status
uv run wealth-pilot status

# Calculate smart buy-only allocation advice for a monthly deposit
uv run wealth-pilot advise --deposit 1500

# Parse and inspect a bank statement or portfolio CSV
uv run wealth-pilot ingest path/to/kbc-export.csv

# Generate a sample generic CSV template
uv run wealth-pilot template --output template.csv
```

---

## Initial Configuration

Wealth Pilot automatically initializes default strategic buckets and configuration in `~/.wealth_pilot/portfolio.yaml`.

You can customize:
- Bucket names, target weights (%), and drift tolerances (±%).
- Manual accounts (e.g. Bunq savings balance, unlisted property value).
- Active debts (mortgage principal balances, interest rate APRs).
