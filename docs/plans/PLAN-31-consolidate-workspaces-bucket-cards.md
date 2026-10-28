# Architecture Plan — Issue #31: Consolidate Workspaces, Responsive Bucket Cards, ETF Tickers & AI Prompt Transparency

- **Issue**: [#31](https://github.com/tiwu/paslood/issues/31)
- **Status**: Implemented (Review Ready)
- **Author**: Antigravity Assistant
- **Target Release**: v0.9.1

---

## 1. Context & Motivation

Historical review `docs/reviews/UX-REVIEW.md` identified findings **UX-04** (part 2), **UX-06**, and **UX-07** (part 2):
1. **UX-06 (Information Architecture Fragmentation & Redundant Bucket Table)**:
   - Paslood's UI had 6 fragmented top-level navigation tabs (`dashboard`, `buckets`, `advice`, `cashflow`, `ai`, `settings`). Balance sheet management was disjointed: real estate and loans were placed at the bottom of data ingestion, while investment holdings were split across buckets and settings.
   - The strategic allocation view featured both a 7-column desktop table and bullet progress meters displaying redundant information.
2. **UX-04 (Asset Tickers in Rebalancing Buy Orders)**:
   - The Smart Buy-Only Rebalancing Calculator recommended euro allocations to underweight buckets (e.g. `+€ 800 Core World ETFs`) without displaying the specific ETF symbols or tickers (e.g. `VWCE.DE`, `IWDA.AS`) mapped to that bucket.
3. **UX-07 (AI Prompt Transparency Drawer)**:
   - While privacy disclosures stated what categories of data were sent to external AI providers, users could not view or audit the exact compiled prompt and numerical figures transmitted over the wire.

---

## 2. Architectural Design & Implementation

### 2.1 Four Core Task Workspaces (+ Settings) (`index.html`, `core.js`)
Consolidated the application navigation into 4 task-oriented workspaces plus settings:
1. **Overview (`#tab-overview`)**: High-level wealth telemetry, KPI summary strip, 30-year net worth projection chart, and FI milestones.
2. **Portfolio & Buckets (`#tab-portfolio`)**: Unified balance sheet containing:
   - Allocation Visualizer & Tolerances with responsive **Bucket Cards** (mode toggle: Bullet track vs. Diverging Drift chart).
   - Real Estate & Manual Assets management (`#manual-assets-tbody`).
   - Mortgages & Liabilities management (`#manual-liabilities-tbody`).
   - Portfolio Holdings & Bucket Assignment mapping table (`#holdings-mapping-tbody`).
   - Top-level PDT Sync and + Add Asset/Loan quick action buttons.
3. **Plan & Rebalance (`#tab-plan`)**:
   - Smart Buy-Only Rebalancing Calculator (`#tab-advice`).
   - Consolidated Debt Payoff vs. Invest priority queue.
   - Belgian 2026 Capital Gains Tax & Fiscal Shield Simulator.
   - Pluggable AI Strategic Financial Advisor (`#tab-ai`).
4. **Cashflow & Import (`#tab-cashflow`)**:
   - Bank/Broker statement CSV ingestion dropzone (`#dropzone`).
   - Transaction ledger with interactive inline re-categorization (`#tx-table-body`).
5. **Account & Settings (`#tab-settings`)**:
   - PDT MCP OAuth connection, AI model selection, encrypted vault backups.

Backward compatibility: `core.js` supports `TAB_ALIASES` (`dashboard` -> `overview`, `buckets` -> `portfolio`, `advice` -> `plan`, `ai` -> `plan`), so hash links and automated tests targeting legacy IDs resolve seamlessly.

### 2.2 Responsive Bucket Cards (`buckets.js`)
- Merged the redundant 7-column table into responsive **Bucket Cards** inside `#bucket-meters-container`.
- Each card incorporates:
  - Bucket name, color dot, status badge (`BALANCED`, `UNDERWEIGHT`, `OVERWEIGHT`), and target % input.
  - Value, actual weight %, drift (€), and tolerance corridor metrics strip.
  - Bullet meter track with shaded tolerance corridor, current weight fill bar, and crisp white target pin marker.
  - Embedded mapped holdings chips displaying ticker, holding name, and live value.

### 2.3 Mapped ETF Tickers in Buy Orders (`guidance.js`, `locales/*.json`)
- Updated `calculateContributionAdvice()` in `guidance.js` to cross-reference `currentData.assets` by `bucket_id`.
- Renders mapped security symbols (e.g. `VWCE.DE`, `IWDA.AS`, `ASML`) as styled badges in buy order recommendation cards.

### 2.4 AI Prompt Transparency Drawer (`routers/ai.py`, `guidance.js`, `index.html`)
- Added endpoint `GET /api/ai/prompt-preview`:
  - Compiles the exact system prompt and financial metrics using `AdviseAiUseCase._build_prompt` without dispatching external LLM network requests.
  - Applies guardrail validation (`_validate_question`) rejecting prompt injection and queries exceeding 1,000 characters with HTTP 400.
- Updated `POST /api/ai/advise` to include `prompt` in its response payload.
- Added collapsible `<details id="ai-prompt-transparency-drawer">` in `index.html` with `<pre id="ai-prompt-preview">` and `Copy Payload` button.

---

## 3. Verification & Metrics

- 202/202 pytest test suite passing with 92% code coverage.
- 7/7 frontend integrity DOM contract tests passing (`tests/delivery/test_frontend_integrity.py`).
- 7/7 Playwright headless Chromium E2E browser tests passing (`tests/e2e/test_ui_workflows.py`).
- Exact i18n key parity across `en.json`, `nl.json`, `fr.json`, `de.json` verified.
- `index.html` maintained under 1900 lines (1888 lines).
- 100% ruff check and format check compliance.
- MkDocs documentation built with `--strict` without errors.
