# Getting Started with Wealth Pilot

Follow this guide to get Wealth Pilot running on your machine or home server in minutes.

---

## 1. Quickstart: Choose Your Deployment Method

You can run Wealth Pilot either directly via Python (`uv`) on your local machine, or inside a Docker container.

### Option A: Local Run via `uv` (Recommended for Local Workstations)

#### Prerequisites
- **Python 3.11+**
- [`uv`](https://docs.astral.sh/uv/) installed:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

#### Setup & Launch
```bash
# Clone repository
git clone https://github.com/tiwu/wealth-pilot.git
cd wealth-pilot

# Install all dependencies
uv sync --all-extras --dev

# Launch the Web Dashboard
uv run wealth-pilot web
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

### Option B: Docker Compose (Recommended for Home Servers & Remote Access)

#### Prerequisites
- **Docker Engine $\ge 24.0$** & **Docker Compose $\ge 2.20$**

#### Setup & Launch
```bash
# Clone repository
git clone https://github.com/tiwu/wealth-pilot.git
cd wealth-pilot

# Configure environment
cp .env.example .env
openssl rand -hex 32  # Copy to WEALTH_PILOT_SECRET_KEY in .env

# Set master admin password
docker compose run --rm wealth-pilot set-password

# Start container
docker compose up -d
```

Open your browser at [http://localhost:8000](http://localhost:8000) and sign in.

---

## 2. Initial Setup & Onboarding Wizard

When you open Wealth Pilot for the first time:

1. **Interactive Setup Wizard**:
   Click **🚀 Setup** in the top navigation bar.
   - **Step 1: Import Portfolio**: Upload your KBC Bank export or generic CSV ledger, or link Portfolio Dividend Tracker via MCP.
   - **Step 2: Define Macro Allocation Buckets**: Customize target allocations (e.g. Core ETFs 50%, Tech/Growth 35%, Gold 5%, Cash Buffer 10%). Total must equal 100%.
   - **Step 3: Regional Tax & AI Preferences**: Set your Belgian capital gains exemption (default: €10,000) and optional AI advisor credentials.

2. **Mobile Phone & Remote Access**:
   - Wealth Pilot has a built-in mobile bottom navigation bar and PWA support.
   - On iOS (Safari) or Android (Chrome), tap **Share** $\rightarrow$ **Add to Home Screen**.
   - To access outside your home network securely without port forwarding, see the [Self-Hosting & Remote Access Guide](self-hosting.md) to enable **Tailscale** or **Cloudflare Tunnel**.

---

## 3. Data Storage & Privacy

All application data is stored locally in your data directory:
- Local default: `~/.wealth_pilot/`
- Docker default: mounted to `/data`
- Configurable via environment variable: `WEALTH_PILOT_DATA_DIR`

Key files created in this directory:
- `portfolio.yaml`: User strategic buckets, asset rules, manual accounts, and liabilities.
- `rules.yaml`: Custom transaction categorization rules.
- `wealth_pilot.db`: SQLite database storing historical transactions, cashflow cache, and discovered holdings (WAL mode enabled).
- `auth.db`: SQLite authentication database with encrypted session tokens and user accounts.
- `.secret_key`: 32-byte master key for envelope encryption (`SecretVault`).

All third-party credentials and AI keys are encrypted with **AES-256-GCM** before being written to disk.

---

## 4. Scriptable CLI Commands

Wealth Pilot includes a rich terminal CLI for quick health checks and headless operations:

```bash
# View consolidated Balance Sheet, Net Worth, and Allocation Drift
uv run wealth-pilot status

# Calculate smart buy-only allocation advice for a monthly deposit
uv run wealth-pilot advise --deposit 2000.0

# Set or update master remote access password
uv run wealth-pilot set-password

# Parse and inspect a bank statement or portfolio CSV
uv run wealth-pilot ingest path/to/kbc-export.csv

# Generate a sample generic CSV template
uv run wealth-pilot template --output template.csv
```
