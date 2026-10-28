# Architecture Plan: Retroactive Categorization Rules and Multi-File Upload Feedback

| Metadata | Details |
| :--- | :--- |
| **Issue** | [#38](https://github.com/tiwu/paslood/issues/38) |
| **Status** | `Approved` |
| **Branch** | `feature/issue-38-featcashflow-retroactive-categorization-` |
| **Author** | Antigravity Agent |
| **Date** | 2026-10-28 |

---

## 1. Problem Statement & User Value

1. **Retroactive Rule Application**:
   - In `POST /api/transactions/rebucket`, selecting "Remember this rule" only saves a pattern to `rules.yaml` and updates the single target `transaction_id`. All matching historical transactions remain in their old categories.
   - For KBC card transactions where `counterparty_name` is empty or merchants containing `*` (`GOOGLE*GOOGLE PLAY APP`, `NYX*VendingWork`), rules must safely match substring patterns across both `counterparty_name` and `description`.
   - The user needs an editable match pattern input in the rebucket modal and immediate retroactive application across earlier transactions.
2. **Upload Feedback & Multi-File Support**:
   - Uploading a CSV file provided minimal visual feedback on how many transactions or assets were created.
   - Selecting multiple files simultaneously was not supported on `#csv-file-input`.
   - The user needs multi-file selection (`multiple` attribute), client-side file header peeking for accurate endpoint selection (`/api/ingest/kbc`, `/api/ingest/bunq`, `/api/ingest/generic`), and clear summary feedback via `showToast()` and the `#upload-status` banner.

---

## 2. Technical Design & Clean Architecture

### 2.1 Domain & Use Case Layer
- **`src/paslood/use_cases/categorize_transactions.py`**:
  - Handle literal `*` in match regex by escaping regex metacharacters when matching simple merchant names, preventing regex syntax errors.
  - Match against `counterparty_name` or `description` when matching rules.
- **`src/paslood/use_cases/ports.py`**:
  - Add `apply_rule_to_transactions(pattern: str, category: str, exclude_overrides: bool = True) -> int` to database port protocol.

### 2.2 Adapters Layer (`src/paslood/adapters/repositories/local_db.py`)
- Implement `apply_rule_to_transactions(pattern: str, category: str, exclude_overrides: bool = True) -> int`:
  - Executes SQL update matching `counterparty_name LIKE '%pattern%' OR description LIKE '%pattern%'`.
  - Skips rows where `user_override = 1` unless specifically updating the selected transaction.
  - Returns count of updated rows.

### 2.3 Delivery Layer
- **`src/paslood/delivery/web/routers/ingestion.py`**:
  - Update `RebucketRequest` to accept `pattern: str | None = None`.
  - When `remember_rule` is true, invoke `db.apply_rule_to_transactions(pattern, target_category)` and return `updated_count`.
- **`src/paslood/delivery/web/templates/index.html` & `static/js/assets_cashflow.js`**:
  - Add `multiple` to `#csv-file-input` and handle `Array.from(files)`.
  - In `openRebucketModal(txId)`, add editable pattern input field defaulted to counterparty or cleaned description.
  - In `saveRebucketRule()`, send `pattern` and report feedback toast: `"Updated X historical transactions to Y"`.
  - Update `detectCsvEndpoint(file)` to peek the first 1KB of content for accurate routing (`bunq`, `kbc`, `positie-overzicht`/generic).
  - Update `#upload-status` banner with per-file and cumulative breakdown (new vs duplicate transactions, discovered assets).

---

## 3. Verification Plan
- Unit test `apply_rule_to_transactions` in `tests/unit/test_local_db.py`.
- Delivery test `POST /api/transactions/rebucket` with retroactive updates and wildcard characters.
- Frontend integrity tests `tests/delivery/test_frontend_integrity.py`.
- Playwright E2E tests `tests/e2e/test_ui_workflows.py`.
