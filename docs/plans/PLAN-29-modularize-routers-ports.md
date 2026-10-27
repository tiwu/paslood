# Architecture Plan — Issue #29: Modularize app.py into APIRouters & Establish Repository Ports

- **Issue**: [#29](https://github.com/tiwu/paslood/issues/29)
- **Status**: Implemented (Review Ready)
- **Author**: Antigravity Assistant
- **Target Release**: v0.9.1

---

## 1. Context & Motivation

In the historical `docs/reviews/ARCHITECTURE-REVIEW.md`, findings **ARCH-03**, **ARCH-04**, and **Split-Brain Persistence** noted:
1. `app.py` was a monolithic delivery controller (1,897 lines) defining 40+ endpoints inside a single closure `create_app()`.
2. Process-global mutable state (`pending_oauth` and `state["pdt_assets"]`) introduced concurrency vulnerabilities and state loss on restart.
3. Lack of abstract repository ports (`typing.Protocol`) violated Clean Architecture layer isolation.

## 2. Proposed Architecture & Remediation

### 2.1 Modular APIRouters
Delivery routes are split into dedicated routers under `src/paslood/delivery/web/routers/`:
- `routers/auth.py`: `/login`, `/auth/login`, `/auth/logout`, Social OAuth flows (`google`, `github`, `meta`).
- `routers/portfolio.py`: `/api/overview`, `/api/buckets/*`, `/api/assets/*`, `/api/liabilities/*`.
- `routers/planning.py`: `/api/advice/*`, `/api/tax/*`, `/api/milestones`, `/api/projection`.
- `routers/ingestion.py`: `/api/ingest/*`, `/api/transactions/*`, `/api/data/*`.
- `routers/ai.py`: `/api/ai/*`.
- `routers/settings.py`: `/api/settings/*`, `/api/backup/*`, `/api/i18n/*`, `/api/mcp/*`.

`app.py` is shrunk from 1,897 lines down to 230 lines, focusing purely on middleware orchestration and router mounting.

### 2.2 Repository Ports Protocol
Pure Python `typing.Protocol` interfaces in `src/paslood/use_cases/ports.py`:
- `PortfolioRepository`: Manages user buckets, manual assets, liabilities, milestones, and settings.
- `TransactionRepository`: Manages ledger transactions, discovered assets, liabilities, and monthly cashflow.

### 2.3 Elimination of In-Memory Volatile State
- SQLite `discovered_assets` now stores PDT MCP holdings on sync/callback and removes them on disconnect.
- OAuth PKCE state tokens are persisted in `oauth_states` table in `auth.db` with a 10-minute TTL, eliminating the in-memory `pending_oauth` dictionary.

---

## 3. Verification & Metrics

- 193/193 unit and integration tests passing.
- 14/14 frontend integrity and Playwright E2E browser tests passing.
- 92% total test coverage across `src/paslood/`.
- 100% ruff lint and format check compliance.
