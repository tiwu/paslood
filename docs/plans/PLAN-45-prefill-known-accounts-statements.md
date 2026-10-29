# Architecture Plan: Prefill Known Accounts from Uploaded Statements & Prompt on New Account Upload

**Issue**: [#45](https://github.com/tiwu/paslood/issues/45)  
**Status**: Plan Drafted  
**Author**: Antigravity  

---

## 1. Context & Motivation

In Issue #43, we added `KnownAccount` domain models, repository persistence in `portfolio.yaml`, and custom account classification for inter-account money flows (transfers to/from investment accounts -> `INVESTMENTS`, savings -> `SAVINGS`, checking -> `TRANSFER`).

However, users currently must manually type their account numbers and IBANs into the Settings form. 
Furthermore, when users upload CSV statements (e.g. Bunq, KBC, Credit Cards) containing accounts that have not yet been registered or labeled, the system processes them without offering a quick action to label and map the newly discovered account.

## 2. Requirements & UX Specifications

1. **Discovered Accounts Retrieval & Prefill in Settings**:
   - Provide an API endpoint `GET /api/accounts/discovered` (or include in `GET /api/overview`) returning all unique account identifiers discovered in transactions and statements:
     - Discovered account numbers / IBANs (from `transactions.account_id` and `discovered_assets`).
     - Inferred institution (e.g. `bunq`, `kbc`, `kbc_credit_card`).
     - Transaction count or latest balance associated with the account.
     - Whether the account is already registered as a `KnownAccount`.
   - In Settings > Known Accounts:
      - When unmapped discovered accounts exist, display quick-add suggestion chips or a dropdown prompt:
        *"Discovered in statements: NL00BUNQ0000000000 (Bunq) [+ Add to Known Accounts]"*.
      - In the "Register Known Account" form, provide an HTML `<datalist>` or quick-select for the Account Number input populated with all discovered accounts, auto-filling suggested Institution and Label when selected.

2. **Upload Feedback & Prompt for New Accounts**:
   - During statement ingestion (`/api/ingest/kbc`, `/api/ingest/bunq`, etc.), check if the ingested account(s) are already present in `known_accounts`.
   - If one or more ingested accounts are not yet known, return `unregistered_accounts: list[dict]` in the ingestion API response with `account_number`, `institution_hint`, and `suggested_label`.
   - In the frontend upload handler (`uploadFiles` in `assets_cashflow.js`):
     - If `unregistered_accounts` are detected, display an interactive notification banner or prompt with a one-click button:
       *"New account detected: NL00BUNQ0000000000 (bunq). [Register Account]"*.
     - Clicking the prompt opens the Known Accounts registration dialog (or a modal) with the account number, institution, and default label prefilled.

3. **Clean Architecture Compliance**:
   - **Domain**: Pure Python entities remain untouched or minimal (`KnownAccount`).
   - **Repository / Database**: Add `LocalDbRepository.get_discovered_account_summaries()` querying distinct `account_id` from transactions and `discovered_assets`.
   - **Delivery / Routers**:
     - `GET /api/accounts/discovered` in `settings.py` or `portfolio.py`.
     - Update ingestion endpoints to return `unregistered_accounts`.
     - Frontend updates in `settings_wizard.js` and `assets_cashflow.js`.

---

## 3. Test-Driven Development (TDD) Plan

1. **Unit & Integration Tests**:
   - `tests/unit/test_discovered_accounts.py`: Verify `LocalDbRepository.get_discovered_account_summaries()` groups and summarizes accounts from transactions and assets.
   - `tests/delivery/test_discovered_accounts_api.py`: Verify `GET /api/accounts/discovered` and `unregistered_accounts` payload on CSV uploads.
2. **Frontend & E2E Tests**:
   - Verify zero console errors in Playwright tests (`tests/e2e/test_ui_workflows.py`).
   - Verify frontend syntax and integrity in `tests/delivery/test_frontend_integrity.py`.
