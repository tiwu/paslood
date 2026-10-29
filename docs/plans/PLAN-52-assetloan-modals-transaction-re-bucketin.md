# Architecture Plan: [Issue #52] Asset/Loan Modals, Re-Bucketing (Keyword + Amount), Amount Filter, Cashflow Period & Historical Trajectory

- **Issue**: [#52](https://github.com/tiwu/paslood/issues/52)
- **Status**: Completed
- **Author**: Autonomous Agent / Contributor
- **Date**: 2026-10-29
- **Target Branch**: `feature/issue-52-assetloan-modals-transaction-re-bucketin`

---

## 1. Problem Statement & Motivation

This plan addresses 9 user-facing bugs and workflow limitations across the Overview, Portfolio, and Cashflow workspaces:

1. **Manual Asset Cost Basis & Acquisition Date Not Displayed or Retained**:
   - Saving an asset with `acquisition_date` or `cost_basis` showed a success notification, but values were not returned by `BuildPortfolioOverviewUseCase.execute()` in `asset_list`, omitted from `renderManualAssetsAndDebts`, and not normalized to `float` during YAML serialization.
2. **Step Validation Warnings on Loan and Asset Number Inputs**:
   - Form inputs with `step="1000"`, `step="100"`, or `step="25"` triggered native browser validation errors (e.g. rejecting monthly payment `290.37` because it was not a multiple of 25).
3. **Truncated Re-Bucket Keywords**:
   - `openRebucketModal()` truncated transaction descriptions to the first word (`desc.split(/[\s-]/)[0]`), losing merchant context, and backend rules matched only on `counterparty_name`.
4. **No Amount-Based Re-Bucketing**:
   - Users could not categorize recurring transactions by amount or combine a keyword with an exact amount.
5. **Internal Savings & Broker Transfers Misclassified**:
   - Transfers to personal savings accounts (e.g. Bunq, KBC Spaarrekening) or brokerages defaulted to generic `TRANSFER` or `LIVING_EXPENSES` instead of `SAVINGS` or `INVESTMENTS`.
6. **No Amount Filter in Recent Transactions**:
   - The transaction search box only supported substring matching and could not filter by amount thresholds (e.g. `>500`, `<=50`).
7. **Fixed Timeframe for Cashflow Visualizations**:
   - The Sankey diagram and Monthly Spending chart only reflected all-time aggregates without timeframe filtering.
8. **Ambiguous Monthly Cashflow Window**:
   - The Monthly Free Cashflow KPI lacked clear window attribution and did not allow toggling between full history and the trailing 12 months.
9. **Compound Wealth Trajectory Chart Omitted Historical Timeline on Initial Load**:
   - Initial page load started the chart at year 0 (`Today`), requiring users to manually change projection settings before historical inception years were displayed.

---

## 2. Requirements & Acceptance Criteria

- [x] Persist `acquisition_date` and `cost_basis` in `portfolio.yaml`, return them in `/api/overview`, and display them in the Manual Assets table and edit modal.
- [x] Use `step="any"` for decimal monetary/rate inputs (and `step="1"` for duration months) across loan and asset modals.
- [x] Retain the full counterparty name or description in the Re-Bucket modal, matching rules across `description`, `counterparty_name`, and `counterparty_iban`.
- [x] Support optional `amount` matching in `POST /api/transactions/rebucket`, `ConfigRepository`, `CategorizeTransactionsUseCase`, and `LocalDbRepository`.
- [x] Classify internal transfers to savings accounts as `SAVINGS` and to brokerages as `INVESTMENTS`.
- [x] Support comparison operators (`>`, `<`, `>=`, `<=`, `=`) and combined text+amount queries in the transaction filter.
- [x] Provide a timeframe selector (`Month`, `Last Year (12M)`, `All Time`) on Cashflow charts and Overview KPI.
- [x] Display the date range and number of months analyzed for Monthly Free Cashflow, with support for `cashflow_period="year"` capped at 12 calendar months.
- [x] Automatically detect portfolio inception date on initial load so historical trajectory displays immediately.
- [x] Automated test suite passes with $\ge 90\%$ code coverage.

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/paslood/domain/`)
- `balance_sheet.py`: Added `period: str = "all"`, `period_start: str | None = None`, and `period_end: str | None = None` to `MonthlyCashflow`.

### 3.2 Use Cases Layer (`src/paslood/use_cases/`)
- `categorize_transactions.py`:
  - Added multi-field matching (`any`, `counterparty_name`, `description`, `counterparty_iban`) and optional `amount` tolerance matching (`±€0.01`).
  - Added heuristic classification for transfers to savings (`SPAARREKENING`, `SPAREN`, Bunq savings) and brokerages (`SAXO`, `BOLERO`, `DEGIRO`, etc.).
- `build_overview.py`:
  - Serialized `acquisition_date`, `cost_basis`, and `cost_basis_formatted` on asset dictionaries.
  - Resolved `oldest_detected_year` using `FindOldestDateUseCase` when `start_year is None` so historical data renders on first load.
  - Propagated `cashflow_period` to `consolidate_balance_sheet` and `build_cashflow_analytics`.

### 3.3 Adapters & Repositories (`src/paslood/adapters/`)
- `config_repo.py`:
  - Converted `current_value` and `cost_basis` to `float` in `save_manual_asset()` to prevent YAML serialization errors with `Decimal`.
  - Deduplicated transaction rules by composite key `(pattern, amount)`.
- `local_db.py`:
  - Extended `apply_rule_to_transactions()` to filter on `amount` when provided.
  - Implemented `filter_transactions_by_period()` supporting `"all"`, `"year"` (trailing 12 calendar months), and `"month"`.
  - Added `period`, `period_start`, and `period_end` metadata to `get_monthly_cashflow()`.

### 3.4 Delivery Layer (`src/paslood/delivery/`)
- `routers/portfolio.py`: Added `cashflow_period: str = "all"` query parameter to `GET /api/overview`.
- `routers/ingestion.py`: Added optional `amount: Decimal | None = None` to `RebucketRequest`, honoring explicitly empty patterns when matching by amount only.
- `templates/index.html` & `static/js/`:
  - Replaced restrictive numeric input steps with `step="any"` in loan and asset modals.
  - Displayed acquisition date and cost basis in `renderManualAssetsAndDebts()`.
  - Added `Match Amount (€)` input to the Re-Bucket modal.
  - Implemented `parseAmountFilterTokens()` and `matchesAmountFilter()` in `assets_cashflow.js`.
  - Added timeframe toggle controls for Cashflow visualizations and the Overview KPI card.
  - Called `populateStartYearSelect(data)` in `renderDashboard()` on initial page load.

---

## 4. Test-Driven Development (TDD) Verification

1. **Unit Tests (`tests/unit/test_issue_52_fixes.py`)**:
   - Asset serialization with cost basis and acquisition date.
   - Rule matching on keyword + amount and amount-only conditions.
   - Internal savings/investment flow classification.
   - Cashflow period filtering and 12-month cap.
   - Automatic inception year detection.
2. **Delivery Integration Tests (`tests/delivery/test_issue_52_delivery.py`)**:
   - `POST /api/assets/manual` persistence and return via `GET /api/overview`.
   - `POST /api/transactions/rebucket` with keyword + amount.
   - `GET /api/overview?cashflow_period=year` cashflow breakdown filtering.
   - HTML step attribute verification.
3. **Frontend & E2E Tests**:
   - `tests/delivery/test_frontend_integrity.py`: Node.js syntax and harness tests for amount filtering, re-bucket prefill, and asset metadata rendering.
   - `tests/e2e/test_ui_workflows.py`: Playwright headless browser tests.

---

## 5. Verification & Rollout Checklist

- [x] Linters pass: `uv run ruff check src tests`
- [x] Formatting passes: `uv run ruff format --check src tests`
- [x] Documentation builds: `uv run mkdocs build --strict`
- [x] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [x] `CHANGELOG.md` updated under `[Unreleased]`
- [x] PR submitted with `Closes #52` and plan linked

