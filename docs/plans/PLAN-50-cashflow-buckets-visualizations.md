# Architecture Plan: [Issue #50] Cashflow Categories, Retroactive Rules, Known Accounts Editing, Savings-Only Cash Buffer & Cashflow Visualizations

- **Issue**: [#50](https://github.com/tiwu/paslood/issues/50)
- **Status**: Approved
- **Author**: Autonomous Agent / Contributor
- **Date**: 2026-10-29
- **Target Branch**: `cashflow-improvements`

---

## 1. Problem Statement & Motivation

Several enhancements and bug fixes are required across the **Cashflow & Import**, **Overview**, **Portfolio & Buckets**, and **Settings** workspaces:

1. **Cashflow & Import — Expanded Expense Categories**:
   - Additional expense categories are needed: `TAX`, `UTILITIES`, `LEISURE`, and `TRANSPORT`.
2. **Cashflow & Import — Retroactive Categorization Across Matching Rows**:
   - When an expense is categorized in the UI, the classification must be applied to other matching rows in the transaction ledger as well.
3. **Cashflow & Import — Known Bank Accounts Recognition (Even With Spaces)**:
   - Known bank accounts must be automatically recognized and classified even when account numbers / IBANs contain spaces, and saving/updating a known account must retroactively classify existing transactions in the ledger (including Bunq counterparty IBANs).
4. **Settings — Edit Known Bank Accounts**:
   - Known bank accounts can currently only be created or deleted; users need to be able to edit existing known accounts (label, IBAN, account type, institution).
5. **Overview Page — Monthly Free Cashflow Explanation & Real Calculation**:
   - The Monthly Free Cashflow KPI number is shown without explaining how it is calculated (`Avg Monthly Income - Fixed Costs - Debt Payments - Living Expenses = Free Cashflow`), and needs to reflect actual categorized transaction averages when statements are imported.
6. **Portfolio & Buckets — Savings-Only Cash Buffer (Option A) & Bucket Assignment Fix**:
   - **Option A Cash Buffer Strategy**:
     - `Cash & Emergency Buffer` bucket represents intentional **Savings** accounts only (`SAVINGS` known accounts / savings assets).
     - Operational `CHECKING` / `CREDIT_CARD` accounts and noisy **PDT Broker Cash** (`pdt-cash*`) are excluded from strategic bucket allocation & holdings mapping so day-of-month checking swings and broker cash drift do not distort portfolio weights.
   - **Bug Fix**: Assigning a Bunq account (or any asset without a unique ticker symbol) to a bucket silently failed to persist because the frontend sent `asset_name` while the backend expected `name`, and `ConfigRepository.assign_asset_to_bucket` matched on generic `symbol="CASH"` instead of specific asset/account identifiers.
7. **Visualizations — Cashflow Sankey Flow & Monthly Spending / Savings Potential**:
   - Add a **Sankey / Flow Diagram** visualizing how monthly income flows into Investments, Savings, Debt Servicing, Fixed Costs, and Living/Discretionary Expenses.
   - Add a **Monthly Spending & Savings Potential** visualization showing month-over-month spending by category and highlighting where monthly savings can be made.

---

## 2. Requirements & Acceptance Criteria

- [x] `TransactionCategory` includes `TAX`, `UTILITIES`, `LEISURE`, `TRANSPORT` with Belgian/European merchant heuristics (`DEFAULT_PATTERNS`) and localized UI badges/filters (`EN`, `NL`, `FR`, `DE`).
- [x] Categorizing a transaction updates the target row and retroactively updates all other matching rows in SQLite.
- [x] Known accounts match IBANs/account numbers regardless of spaces across `counterparty_iban`, `account_id`, `description`, and `counterparty_name`, and saving/updating a known account retroactively re-categorizes matching transactions.
- [x] Known accounts can be edited in Settings via an Edit action and `PUT /api/accounts/known/{account_id}` / `POST /api/accounts/known`.
- [x] Overview KPI card displays an explicit breakdown of how Monthly Free Cashflow is calculated (`Income - Fixed - Debt - Living = Surplus`).
- [x] Option A Cash Buffer: Only `SAVINGS` accounts are included as cash holdings for strategic buckets; `CHECKING`, `CREDIT_CARD`, and PDT broker cash are excluded from bucket holdings; assigning a Bunq/savings asset to `cash-buffer` (or any bucket) persists accurately.
- [x] Cashflow page includes an interactive **Income → Outflows & Investments Sankey Diagram** and a **Monthly Spending & Savings Opportunity** chart/analyzer.
- [x] Automated tests cover all cases with $\ge 90\%$ test coverage.

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/paslood/domain/`)
- **`balance_sheet.py`**:
  - Extend `TransactionCategory` with `TAX`, `UTILITIES`, `LEISURE`, `TRANSPORT`.
  - Enrich `MonthlyCashflow` with optional `investments_and_savings: Money`, `months_analyzed: int`, and `is_estimated: bool`.

### 3.2 Use Cases Layer (`src/paslood/use_cases/`)
- **`categorize_transactions.py`**:
  - Add Belgian/European heuristics for `TAX`, `UTILITIES`, `LEISURE`, and `TRANSPORT`.
  - Normalize IBANs / account numbers by stripping spaces and non-alphanumeric characters when matching known accounts.
- **`build_overview.py`**:
  - Filter out operational `CHECKING`/`CREDIT_CARD` cash assets and noisy PDT broker cash (`pdt-cash*` / `AssetClass.CASH` from PDT) from strategic portfolio holdings according to Option A, keeping `SAVINGS` accounts (and manual assets) eligible for `Cash & Emergency Buffer`.
  - Compute `cashflow_breakdown` and `cashflow_analytics` (monthly category series, Sankey flow nodes/links, and savings opportunities).

### 3.3 Adapters & Repositories (`src/paslood/adapters/`)
- **`bunq_csv.py`**:
  - Populate `counterparty_iban` on `Transaction` from the Bunq CSV `Counterparty` column.
- **`local_db.py`**:
  - Update `get_monthly_cashflow()` to compute real monthly category averages from imported transactions when present.
  - Enhance `apply_rule_to_transactions()` to always update matching transactions and add `apply_known_account_to_transactions()` for retroactive classification when known accounts are created or edited.
- **`config_repo.py`**:
  - Fix `assign_asset_to_bucket()` so assets with generic `symbol="CASH"` or empty symbol are matched by specific `name_keywords` / `asset_id` rather than generic `"CASH"`, and clean up any previous rule conflicts across buckets.

### 3.4 Delivery Frameworks (`src/paslood/delivery/`)
- **`routers/portfolio.py`**:
  - Accept both `name` and `asset_name` in `AssignAssetRequest`.
- **`routers/ingestion.py`**:
  - Apply transaction categorization rules across all matching rows in `POST /api/transactions/rebucket`.
- **`routers/settings.py`**:
  - Support editing known accounts via `POST /api/accounts/known` and `PUT /api/accounts/known/{account_id}`, and trigger retroactive transaction reclassification.
- **`templates/index.html` & `static/js/*.js` & `i18n.py`**:
  - Add new categories to filters, modals, badges, and i18n bundles.
  - Add Edit button and form state for Known Accounts in Settings.
  - Add Monthly Free Cashflow formula breakdown on the Overview KPI card.
  - Add Cashflow Sankey diagram and Monthly Spending & Savings Potential charts on the Cashflow page.

---

## 4. Test-Driven Development (TDD) Plan
1. **Red (Tests First)**:
   - Unit tests for new `TransactionCategory` values, heuristics, known account space-insensitive matching, Option A cash filtering, and `assign_asset_to_bucket` for Bunq cash assets.
   - Integration & delivery tests for retroactive re-bucketing, editing known accounts, overview cashflow breakdown, and cashflow analytics payload.
   - Frontend integrity and E2E Playwright tests.
2. **Green (Implementation)**:
   - Implement changes across `domain/`, `use_cases/`, `adapters/`, and `delivery/`.
3. **Refactor & Quality**:
   - Run `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mkdocs build --strict`, and `uv run pytest --cov=src/paslood`.

---

## 5. Verification & Rollout Checklist
- [x] Linters pass: `uv run ruff check src tests`
- [x] Formatting passes: `uv run ruff format --check src tests`
- [x] Documentation builds: `uv run mkdocs build --strict`
- [x] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [x] `CHANGELOG.md` updated under `[Unreleased]`
- [x] PR submitted with `Closes #50` and plan linked
