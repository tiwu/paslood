# Architecture Plan: Cashflow Table Pagination, Multi-Account Filter & Colored Category Badges

| Metadata | Details |
| :--- | :--- |
| **Issue** | [#39](https://github.com/tiwu/paslood/issues/39) |
| **Status** | `Approved` |
| **Branch** | `feature/issue-39-featui-cashflow-table-pagination-multi-a` |
| **Author** | Antigravity Agent |
| **Date** | 2026-10-28 |

---

## 1. Problem Statement & User Value

1. **Table Truncation & Lack of Pagination**:
   - The user uploaded multiple CSV statements totaling over 600 transactions, but the UI only rendered up to 100 transactions due to `txs.slice(0, 100)` in `assets_cashflow.js`, and the SQLite query capped at 1,000 rows.
   - Users need full pagination controls (page size selector: 25 / 50 / 100 / All, First / Previous / Page indicator / Next / Last buttons) and search/category filtering.
2. **Multi-Account Column & Filtering**:
   - When importing multiple accounts (multiple KBC checking accounts, KBC credit card, Bunq spending & savings accounts), transactions do not show which account they originated from.
   - `GET /api/overview` omits `account_id` from the returned transaction objects.
   - Users need an **Account** column displaying a recognizable account badge (e.g. `KBC ••2832`, `KBC ••3108`, `KBC Card ••9128`, `bunq ••9982`, `bunq ••24827`) and an Account filter dropdown.
3. **Internal Transfers Inflating Monthly Income**:
   - Transfer transactions between own savings and checking accounts (`Category.TRANSFER` or `Category.SAVINGS`) were counted as inflow income in monthly cashflow calculations.
   - `local_db.py` must exclude transfers from income calculations.
4. **Distinct Category / Bucket Colors**:
   - All category buttons in the table currently use identical `text-blue-400 bg-slate-800` styling.
   - Distinct semantic colors per category (e.g., emerald for income, lime for groceries, cyan for utilities, indigo for housing, etc.) improve visual hierarchy and readability.
5. **Release Tracking**:
   - Record all changes under `## [Unreleased]` in `CHANGELOG.md` so merging this final PR to `main` triggers `.github/workflows/release.yml`.

---

## 2. Technical Design & Implementation

### 2.1 Backend Serialization (`src/paslood/delivery/web/routers/portfolio.py`)
- In `GET /api/overview` (lines 117–128), add `"account_id": t.account_id` to the serialized transaction dictionaries.
- Increase the transaction fetch limit from `1000` to `10000` so full multi-year statement histories load seamlessly.
- In `src/paslood/adapters/repositories/local_db.py`, exclude `TRANSFER` from `get_monthly_cashflow_summary`.

### 2.2 Frontend Markup & Component Structure (`src/paslood/delivery/web/templates/index.html`)
- In `#tab-cashflow`:
  - Add search input (`#tx-search-input`), category filter dropdown (`#tx-category-filter`), and account filter dropdown (`#tx-account-filter`).
  - Add an **Account** `<th>` to the transactions table.
  - Add responsive pagination footer:
    - `"Showing X–Y of Z transactions"`
    - Page size select (`25`, `50`, `100`, `All`)
    - First, Prev, Page `N / Total`, Next, Last buttons.

### 2.3 Frontend Logic (`src/paslood/delivery/web/static/js/assets_cashflow.js`)
- Maintain pagination and filter state:
  ```javascript
  let txCurrentPage = 1;
  let txPageSize = 25; // or 'all'
  let txSearchQuery = '';
  let txCategoryFilter = 'ALL';
  let txAccountFilter = 'ALL';
  ```
- Implement `formatAccountBadge(accountId)`:
  - Formats IBANs and card numbers into clean, human-friendly badges (`KBC ••2832`, `bunq ••9982`, `KBC Card ••9128`) with full identifier on tooltip.
- Implement `getCategoryBadgeClasses(cat)`:
  - Returns semantic background, border, and text styling for all 10+ transaction categories.
- Implement `renderTransactions()` with client-side filtering and slice-based page rendering.

### 2.4 Precompiled Tailwind Compilation
- Run `npm run build:css` to bundle any new Tailwind color/border utility classes into `src/paslood/delivery/web/static/css/styles.css`.

### 2.5 Changelog Update (`CHANGELOG.md`)
- Populate `## [Unreleased]` in `CHANGELOG.md` with full details across issues #37, #38, and #39 so merging triggers automated release `v0.10.0`.

---

## 3. Verification Plan
- Integration test `test_overview_includes_account_id_and_large_history`.
- Frontend integrity test `tests/delivery/test_frontend_integrity.py`.
- Playwright E2E UI test `tests/e2e/test_ui_workflows.py`.
- Full test suite `uv run pytest`.
- Documentation build `uv run mkdocs build --strict`.
