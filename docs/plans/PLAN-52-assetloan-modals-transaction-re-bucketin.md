# Architecture Plan: [Issue #52] Asset/Loan Modals, Transaction Re-Bucketing (Keyword + Amount), Internal Transfers, Amount Filter, Cashflow Period & Compound Trajectory Start

- **Issue**: [#52](https://github.com/tiwu/paslood/issues/52)
- **Status**: Approved
- **Author**: Autonomous Agent / Contributor
- **Date**: 2026-10-29
- **Target Branch**: `feature/issue-52-assetloan-modals-transaction-re-bucketin`

---

## 1. Problem Statement & Motivation

Several bugs and workflow enhancements were identified across the **Portfolio & Buckets**, **Cashflow & Import**, and **Overview** workspaces:

1. **Edit Asset Screen — Acquisition Date & Original Cost Basis Not Saving / Displaying**:
   - Saving an asset with `acquisition_date` or `cost_basis` in the Edit Asset modal displays a success notification, but after reloading `/api/overview`, the values do not appear in the manual assets table or when re-opening the Edit Asset modal.
   - `BuildPortfolioOverviewUseCase.execute()` builds `asset_list` without serializing `acquisition_date`, `cost_basis`, or `cost_basis_formatted`. Additionally, `ConfigRepository.save_manual_asset` must serialize `Decimal` values to `float` in YAML and allow clearing/updating those fields, and `renderManualAssetsAndDebts` in `assets_cashflow.js` should display the acquisition date and cost basis.

2. **Edit Loan / Mortgage Screen — HTML5 Step Range Validation Warnings**:
   - Inputs with decimal values (e.g., Monthly Fixed Payment `290.37` with `step="25"`, Remaining Principal `8346.34` with `step="100"`, Start Capital `12405` with `step="1000"`) trigger native browser validation tooltips (`Selecteer een geldige waarde. De twee dichtstbijzijnde geldige waarden zijn 275 en 300.`).
   - Using `step="any"` on currency/rate number inputs and `step="1"` on duration months removes false range/step warnings.

3. **Re-Bucket Transaction — Keyword / Merchant Pattern Fallback Issue**:
   - Opening the Re-Bucket modal or saving a changed keyword/merchant pattern falls back to the first word of the description (`desc.split(/[\s-]/)[0]`) or fails to match when `match_field` is hardcoded to `"counterparty_name"` while the user specified a description keyword.

4. **Re-Bucket Transaction — Match on Combination of Keyword and Amount**:
   - Users need the ability to re-bucket transactions based on a combination of **keyword/merchant AND amount** (or amount alone / keyword + amount) so recurring transfers or split payments to the same counterparty with different amounts can be categorized distinctly.

5. **Internal Transfers Between Own Accounts Not Automatically Recognized as Saving / Investing**:
   - Transfers between the user's own accounts (or to savings/investment accounts like KBC Spaarrekening, Bunq savings, Saxo, Bolero, DeGiro, or matching own account holder name / IBANs across imported statements) are categorized as generic `TRANSFER` or `LIVING_EXPENSES` instead of `SAVINGS` or `INVESTMENTS`.

6. **Recent Transactions Table — Filter on Amount (e.g. `>500`, `<100`, `>=250`, `=50`)**:
   - Users need to filter transactions in the Recent Transactions search box using comparison operators like `>500`, `<200`, `>=1000`, `<=50`, or `=250` (supporting both absolute magnitude and signed amounts, as well as comma/dot decimals and combined text + amount queries like `kbc >500`).

7. **Cashflow Page Graphs — Selectable Timeframe (`Month`, `Year`, `All`)**:
   - Add a timeframe selector (`Month`, `Year`, `All`) to the Cashflow visualizations (Sankey flow diagram & Monthly Spending / Savings Opportunities chart) to filter transactions and recompute analytics for the selected period.

8. **Monthly Cashflow Calculation — Clarify Period & Allow Selecting `Last Year` or `All Time`**:
   - Explicitly show which period the Monthly Free Cashflow calculation is based on (`Last 12 Months` vs `All Time`, including the date range and number of months analyzed) and allow the user to switch between `Last Year (12M)` and `All Time` on both the Overview KPI card and the Cashflow workspace.

9. **Compound Wealth Graph — Starts on 'Now' on Initial Page Load**:
   - On initial page load, `/api/overview` calls `BuildPortfolioOverviewUseCase.execute()` without passing `start_year`, so `trajectory` starts at `year = 0` (`Today`). Only after changing a setting or timeframe does `updateProjectionChart()` call `/api/projection` (which runs `FindOldestDateUseCase` and includes historical years).

---

## 2. Requirements & Acceptance Criteria

- [ ] Saving `acquisition_date` and `cost_basis` in the Add/Edit Asset modal persists to `portfolio.yaml`, is returned in `/api/overview`, is displayed in the Manual Assets table, and pre-populates the Edit Asset modal on reload.
- [ ] All numeric inputs in the Edit Loan / Mortgage modal and Add/Edit Asset modal use `step="any"` (or `step="1"` for integer months) so arbitrary decimal amounts never trigger browser step validation warnings.
- [ ] Opening the Re-Bucket modal pre-fills the full counterparty name or full description (never truncating to the first word), and saving a custom keyword/merchant matches across `counterparty_name`, `description`, and `counterparty_iban`.
- [ ] Re-Bucket modal supports an optional **Match Amount (€)** condition; rules with both `pattern` and `amount` only match transactions satisfying both criteria (retroactively in SQLite and in `CategorizeTransactionsUseCase`).
- [ ] Internal transfers to savings accounts (e.g. `SPAARREKENING`, `BUNQ`, known `SAVINGS` accounts, or own-account transfers to savings/bunq IBANs) are automatically categorized as `SAVINGS`, and transfers to investment/broker accounts are categorized as `INVESTMENTS`.
- [ ] Recent Transactions search box supports amount filter expressions (`>500`, `<100`, `>=250`, `<=50`, `=100`, plus combined keyword + amount queries).
- [ ] Cashflow page graphs (Sankey & Monthly Spending) include a timeframe selector (`Month`, `Year`, `All`).
- [ ] Monthly Cashflow calculation clearly states the period (`Last Year` vs `All Time` + months analyzed) and allows switching between `Last Year` (`year`) and `All Time` (`all`).
- [ ] Compound Wealth Trajectory chart includes historical years (`Auto Inception`) immediately on initial page load without requiring a settings change.
- [ ] Automated tests cover all cases with $\ge 90\%$ test coverage.

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/paslood/domain/`)
- **`balance_sheet.py`**:
  - Add `period: str = "all"`, `period_start: str | None = None`, and `period_end: str | None = None` to `MonthlyCashflow`.

### 3.2 Use Cases Layer (`src/paslood/use_cases/`)
- **`categorize_transactions.py`**:
  - Match user rules across `description`, `counterparty_name`, and `counterparty_iban` when `match_field` is `"any"`, `"counterparty_name"`, or `"description"`, and evaluate optional `amount` (matching `abs(tx.amount.amount)` or signed amount within `0.01`).
  - Recognize internal transfers to savings accounts (KBC Spaarrekening, Bunq savings, own-account transfers to savings/bunq IBANs) as `SAVINGS` and to investment accounts as `INVESTMENTS`.
- **`build_overview.py`**:
  - Include `acquisition_date`, `cost_basis`, and `cost_basis_formatted` in `asset_list`.
  - Auto-detect `oldest_detected_year` via `FindOldestDateUseCase` when `start_year is None` so initial `/api/overview` trajectory includes historical years (`calendar_year`, `is_historical`, `is_current`).
  - Support `cashflow_period` (`"all"`, `"year"`, `"month"`) in `consolidate_balance_sheet` and `build_cashflow_analytics`.

### 3.3 Adapters & Repositories (`src/paslood/adapters/`)
- **`config_repo.py`**:
  - Normalize `Decimal` values (`current_value`, `cost_basis`) in `save_manual_asset` to `float` before writing YAML, and allow updating/clearing `acquisition_date` and `cost_basis`.
  - Deduplicate transaction rules in `save_transaction_rule` by `(pattern, amount)` so rules with the same keyword but different amounts are preserved.
- **`local_db.py`**:
  - Update `apply_rule_to_transactions` to accept optional `amount: Decimal | float | None = None` and match `ABS(CAST(amount AS REAL) - ?) < 0.005 OR ABS(ABS(CAST(amount AS REAL)) - ABS(?)) < 0.005`.
  - Update `get_monthly_cashflow(period: str = "all")` to filter transactions to the last 12 months (`"year"`) or latest month (`"month"`) or all time (`"all"`), populating `period`, `period_start`, and `period_end`.

### 3.4 Delivery Frameworks (`src/paslood/delivery/`)
- **`routers/portfolio.py`**:
  - Add `cashflow_period: str = "all"` query parameter to `GET /api/overview`.
- **`routers/ingestion.py`**:
  - Add `amount: Decimal | None = None` to `RebucketRequest` and pass it to `repo.save_transaction_rule` and `db.apply_rule_to_transactions`.
- **`templates/index.html` & `static/js/*.js`**:
  - Set `step="any"` on numeric inputs in `add-liability-modal` and `add-asset-modal`.
  - Render `acquisition_date` and `cost_basis` in `renderManualAssetsAndDebts` and `openAddAssetModal`.
  - Update `openRebucketModal` and `commitRebucket` to preserve the full keyword/merchant and support optional amount matching.
  - Add amount comparison filtering (`>500`, `<100`, `>=250`, `<=50`, `=100`) in `getFilteredTransactions`.
  - Add timeframe selector (`Month`, `Year`, `All`) for Cashflow graphs and period selector (`Last Year`, `All Time`) for Monthly Cashflow calculation.
  - Call `populateStartYearSelect(data)` in `renderDashboard(data)` so the Compound Wealth Trajectory chart renders historical years on initial page load.

---

## 4. Test-Driven Development (TDD) Plan
1. **Red (Tests First)**:
   - Unit tests in `tests/unit/test_issue_52_fixes.py` covering categorization rules with keyword + amount, internal transfer detection as `SAVINGS`/`INVESTMENTS`, `get_monthly_cashflow(period=...)`, and `BuildPortfolioOverviewUseCase` historical trajectory & asset `cost_basis`/`acquisition_date`.
   - Delivery integration tests in `tests/delivery/test_issue_52_delivery.py` covering manual asset edit persistence, re-bucketing with keyword + amount, and `/api/overview?cashflow_period=year`.
   - Frontend integrity tests in `tests/delivery/test_frontend_integrity.py` and E2E Playwright checks in `tests/e2e/test_ui_workflows.py`.
2. **Green (Implementation)**:
   - Implement changes across `domain/`, `use_cases/`, `adapters/`, and `delivery/`.
3. **Refactor & Quality**:
   - Zero lint errors (`uv run ruff check src tests`)
   - Format check (`uv run ruff format --check src tests`)
   - 90%+ coverage (`uv run pytest --cov=src/paslood --cov-fail-under=90`)

---

## 5. Verification & Rollout Checklist
- [ ] Linters pass: `uv run ruff check src tests`
- [ ] Formatting passes: `uv run ruff format --check src tests`
- [ ] Documentation builds: `uv run mkdocs build --strict`
- [ ] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR submitted with `Closes #52` and plan linked
