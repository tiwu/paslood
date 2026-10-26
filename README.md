# Paslood 🧭

> **Whole-Life Balance Sheet, PDT Strategic Companion & Belgian Fiscal Shield**
>
> *"You can't know where you're going if you don't know where you are."*

**Paslood** (*in het lood staan* — plumb-line alignment for your personal balance sheet) is a local-first, privacy-respecting financial decision engine. While broker trackers like **Portfolio Dividend Tracker (PDT)** excel at tracking brokerage holdings and dividends, they are blind to the rest of your financial reality: checking and savings accounts (KBC, Bunq), pillar pension savings (*pensioensparen*), primary residence equity, mortgages, consumer/vehicle loans (e.g., Alpha Credit), and recurring employee share purchase plans (e.g., ASML shares on EquatePlus).

Paslood unifies your PDT portfolio with your off-broker balance sheet to answer **what to do next**: keeping your macro allocation buckets level, prioritizing debt payoff against expected portfolio CAGR, and safely de-concentrating employee stock under Belgian tax law.

---

## Key Features

- **Whole-Life Balance Sheet**: Combines PDT MCP brokerage holdings (Saxo, manual stocks) with KBC/Bunq bank accounts, pension savings, real estate, mortgages, and consumer loans.
- **Strategic Allocation Buckets**: Define macro pillars (Core ETFs, Single-Stock / Employee Shares, Gold & Commodities, Emergency Buffer, Real Estate) with drift tolerances and optional rebalancing exclusion flags.
- **Buy-Only Rebalancing**: Direct incoming savings deposits to underweight buckets to minimize tracking error without selling assets or triggering capital gains taxes.
- **Legally Grounded Belgian Fiscal Shield**:
  - **2026 Meerwaardebelasting (WIB 92 Art. 90/101)**: FIFO lot tracking with `max(Dec 31 2025 Fotomoment, Historical Purchase Price)` loss protection, 5-year exemption carryover (`€10,000` to `€15,000`, doubled for joint filing), and a 1-click **Max Tax-Free Share Trim Solver**.
  - **EquatePlus (Zurich) vs. Belgian Broker Reconciliation**: Reconciles Equatex AG Zurich settlement statements (`0.35%` commission + `0.15%` Swiss stamp duty, historical FMV gain vs. 31 Dec 2025 fotomoment) and flags unwithheld **Belgian TOB (`0.35%`)** requiring bi-monthly MyMinfin self-declaration.
  - **TOB & Reynders Tax (WDRT Art. 120 & WIB 92 Art. 19bis)**: Full support for `0.12%` / `0.35%` / `1.32%` TOB statutory caps and the `30%` Reynders tax on fixed-income/mixed funds (`>10%` debt claims).
- **Consolidated Balance Sheet & Debt Avalanche**: Unified priority queue comparing debt APRs against expected portfolio CAGR (7.0%) alongside active drift alerts.
- **Server-Side AI Advisor**: Pluggable private advisors (Gemini, Claude, GPT-4o, Ollama) with disk envelope encryption; zero client-side credential exposure.
- **Privacy & Security First**:
  - Local SQLite with WAL mode + AES-256-GCM envelope encryption (`SecretVault`).
  - Network bind guard preventing unauthenticated public exposure.
  - Multi-tenant isolation ready for private self-hosting or SaaS.
- **Flexible Delivery**:
  - **Web Dashboard**: Responsive dark-mode dashboard (with mobile bottom navigation & PWA support).
  - **Scriptable CLI**: Direct terminal reporting (`status`, `advise`, `ingest`, `set-password`).
  - **Docker & Remote Access**: Run standalone or containerized with **Tailscale**, **Cloudflare Tunnel**, or **DuckDNS + Caddy**.

---

## Quick Start Options

### Option A: Local Run via `uv` (Fastest for Local Desktop)

Requires Python 3.12+ (3.14 recommended) and [`uv`](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/tiwu/paslood.git
cd paslood

# Install all dependencies
uv sync --all-extras --dev

# Run the Web Dashboard on http://localhost:8000
uv run paslood web

# Run CLI Status Report
uv run paslood status
```

---

### Option B: Containerized via Docker Compose (Recommended for Home Servers & Remote Access)

Requires Docker Engine $\ge 24.0$ & Docker Compose $\ge 2.20$.

```bash
# 1. Clone repository
git clone https://github.com/tiwu/paslood.git
cd paslood

# 2. Copy environment template and generate secret key
cp .env.example .env
openssl rand -hex 32  # Copy output to WEALTH_PILOT_SECRET_KEY in .env

# 3. Set master admin password
docker compose run --rm paslood set-password

# 4. Start Paslood
docker compose up -d
```

Open [http://localhost:8000](http://localhost:8000) and log in.

---

## Remote Access: Mobile Phone & Anywhere Access

Paslood supports three zero-trust and self-hosted remote access setups out of the box:

| Method | Profile | Best For | Port Forwarding Needed? |
| :--- | :--- | :--- | :--- |
| **Tailscale** *(Recommended)* | `--profile tailscale` | Private encrypted WireGuard mesh on phone/laptop | **No** (Most secure) |
| **Cloudflare Tunnel** | `--profile cloudflared` | Browser access via custom domain without VPN app | **No** |
| **DuckDNS + Caddy** | `--profile ddns` | Automatic Let's Encrypt TLS reverse proxy | Yes (Ports 80/443) |

#### Running with Tailscale:
```bash
# Set TAILSCALE_AUTHKEY in .env
docker compose --profile tailscale up -d
```
Access securely from your phone or laptop at `http://paslood:8000`.

See the complete [Self-Hosting & Remote Access Guide](docs/self-hosting.md) for full configuration steps.

---

## Authentication & Security

Paslood includes a secure, built-in identity and session manager:

1. **Master Passphrase Authentication**:
   ```bash
   uv run paslood set-password
   ```
2. **Social OAuth 2.0**:
   Configure `WEALTH_PILOT_GOOGLE_CLIENT_ID`, `WEALTH_PILOT_GITHUB_CLIENT_ID`, or `WEALTH_PILOT_META_CLIENT_ID` in `.env` to enable 1-click social logins.
3. **Email Whitelisting**:
   Restrict access exclusively to authorized users via `WEALTH_PILOT_ALLOWED_EMAILS=alice@example.com,bob@example.com`.
4. **Envelope Encryption**:
   Sensitive API keys and external credentials stored in `portfolio.yaml` are encrypted at rest with AES-256-GCM using per-tenant keys derived via HKDF-SHA256.

---

## CLI Reference

```bash
# Show balance sheet, net worth, and allocation drift
uv run paslood status

# Calculate optimal buy-only distribution for a €2,000 deposit
uv run paslood advise --deposit 2000.0

# Set or update master remote access password
uv run paslood set-password

# Ingest bank statements or broker CSVs
uv run paslood ingest statement.csv

# Generate a sample portfolio import template
uv run paslood template --output template.csv

# Launch Web Dashboard (bind guard prevents unauthenticated 0.0.0.0 exposure)
uv run paslood web --port 8000
```

---

## Clean Architecture Overview

Paslood strictly adheres to **Uncle Bob's Clean Architecture**:

```text
src/wealth_pilot/
├── domain/        # Pure Python enterprise business rules (Money, Asset, Liability, Bucket, Identity)
├── use_cases/     # Application orchestrators (CalculateBucketAllocation, AdviseContribution, BuildOverview)
├── adapters/      # Gateways (PDT MCP, KBC/Generic CSV, SecretVault, Settings, ConfigRepository)
└── delivery/      # Frameworks & Drivers (FastAPI web routes, templates, AuthManager, CLI)
```

---

## Testing & Quality Assurance

```bash
# Run all unit, delivery, and integration tests (126 tests)
uv run pytest

# Run tests with coverage (target >= 90%)
uv run pytest --cov=src/wealth_pilot --cov-report=term-missing

# Lint & code format checks
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts

# Strict documentation build
uv run mkdocs build --strict
```

---

## License

MIT License.
