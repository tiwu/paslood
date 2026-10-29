# Architecture Plan: Known Accounts, Inter-Account Flow Classification & Bunq Holdings Mapping

| Metadata | Details |
| :--- | :--- |
| **Issue** | [#43](https://github.com/tiwu/paslood/issues/43) |
| **Status** | `Approved` |
| **Branch** | `feature/issue-43-feataccounts-link-saxo-external-accounts` |
| **Author** | Antigravity Agent |
| **Date** | 2026-10-28 |

---

## 1. Problem Statement & User Value

1. **Bunq Accounts Missing from Holdings & Bucket Allocation**:
   - Bunq CSV exports lack a `Saldo` running balance column. `BunqCsvGateway` returned a placeholder cash asset with `current_value = Money(0.00)`. Because holdings tables filter `a.current_value > 0`, Bunq accounts never appeared in Holdings or bucket assignment widgets.
   - We must calculate the cumulative statement balance from the transactions (e.g. €150.00 for spending, €5,000.00 for savings), create distinct cash assets per discovered account with `institution="bunq"` and `account_id`, and display them in Holdings with auto-mapping to Cash/Emergency buffer buckets.
2. **Recognizing Saxo & Custom User Accounts**:
   - The user wants to register their Saxo account numbers / IBANs with a label (e.g. "Saxo Trading", "Saxo Investor"), so transactions to/from Saxo are automatically recognized as investment contributions/withdrawals.
   - Users need a "Known Accounts" configuration where they can register external accounts (Saxo, off-broker banks, pension schemes) with `account_number`, `label`, `account_type` (`INVESTMENT`, `SAVINGS`, `CHECKING`), and optional `institution`.
3. **Automated Inter-Account Flow Classification**:
   - Transactions moving money between known user accounts must be categorized automatically based on the target account type:
     - Outflow to `INVESTMENT` (e.g. Saxo) -> `INVESTMENTS` ("Investing")
     - Inflow from `INVESTMENT` (e.g. Saxo) -> `INVESTMENTS` ("Withdrawal")
     - Outflow to `SAVINGS` (e.g. Bunq Savings / KBC Savings) -> `SAVINGS` ("Saving")
     - Inflow from `SAVINGS` -> `SAVINGS` ("Unsaving")
     - Transfers between two `CHECKING` accounts -> `TRANSFER` ("Internal Transfer")

---

## 2. Technical Design & Clean Architecture

### 2.1 Domain & Use Case Layer
- **`src/paslood/domain/account.py`**:
  - Add `KnownAccount` entity:
    ```python
    @dataclass(frozen=True)
    class KnownAccount:
        id: str
        account_number: str  # IBAN or account reference
        label: str           # e.g. "Saxo Trading"
        account_type: str    # "INVESTMENT", "SAVINGS", "CHECKING"
        institution: str = ""
    ```
- **`src/paslood/use_cases/categorize_transactions.py`**:
  - Accept `known_accounts: Sequence[KnownAccount]` in `execute()`.
  - For each transaction, check if `counterparty_iban`, `counterparty_name`, or `description` matches any known account's `account_number`.
  - If a match is found, apply flow categorization:
    - Target `INVESTMENT` -> `TransactionCategory.INVESTMENTS`
    - Target `SAVINGS` -> `TransactionCategory.SAVINGS`
    - Target `CHECKING` -> `TransactionCategory.TRANSFER`
  - In addition, check natural language keywords (`spaarrekening`, `overschrijving naar eigen rekening`, `epargne`) for saving/unsaving.

### 2.2 Adapters Layer
- **`src/paslood/adapters/ingestion/bunq_csv.py`**:
  - Calculate cumulative balance per account from parsed transactions:
    `account_balances[acc_id] += amount_dec`.
  - Return `discovered_cash_assets: list[Asset]`, each with `id=f"bunq-cash-{acc_id}"`, `name=f"bunq ({acc_id})"`, `current_value=Money(balance, "EUR")`, `institution="bunq"`, `account_id=acc_id`.
  - Update `POST /api/ingest/bunq` in `routers/ingestion.py` to save all discovered cash assets into SQLite.
- **`src/paslood/adapters/repositories/config_repo.py`**:
  - Add `load_known_accounts() -> list[KnownAccount]`.
  - Add `save_known_account(account: KnownAccount) -> None`.
  - Add `delete_known_account(account_id: str) -> None`.
  - Persist under `known_accounts` list in `portfolio.yaml`.

### 2.3 Delivery Layer
- **`src/paslood/delivery/web/routers/settings.py`**:
  - Add endpoints:
    - `GET /api/accounts/known`
    - `POST /api/accounts/known`
    - `DELETE /api/accounts/known/{account_id}`
- **`src/paslood/delivery/web/templates/index.html` & `static/js/settings_wizard.js` / `assets_cashflow.js`**:
  - Add "Known Accounts & Inter-Account Transfers" card in Settings.
  - Form to add account (Account number / IBAN, Label, Type: Investment / Savings / Checking, Institution).
  - List of registered accounts with delete actions.
  - In `assets_cashflow.js`, match known accounts in `formatAccountBadge` so transactions with Saxo or other known accounts display the customized label (e.g. `Saxo Trading ••1234`).
- **`CHANGELOG.md`**:
  - Document all additions under `## [Unreleased]` to trigger automated release on merge.

---

## 3. Verification Plan
- Unit tests in `tests/unit/test_known_accounts.py` verifying known account persistence and flow categorization.
- Integration tests in `tests/integration/test_ingestion_csv_formats.py` verifying Bunq balances are calculated and saved to discovered assets with positive values.
- Delivery API tests verifying `/api/accounts/known` endpoints.
- Frontend integrity test `tests/delivery/test_frontend_integrity.py`.
- Playwright E2E UI test `tests/e2e/test_ui_workflows.py`.
