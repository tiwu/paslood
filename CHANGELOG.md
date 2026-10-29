# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Clean Architecture Boundary & Port Alignment (#47)**:
  - Added `@runtime_checkable` `AIAdvisorPort` and `StatementGatewayPort` protocols in `src/paslood/use_cases/ports.py` and aligned `PortfolioRepository` and `TransactionRepository` method signatures with `ConfigRepository` and `LocalDbRepository`.
  - Added `BalanceSheet.with_effective_assets(buckets, exclude_property)` in `src/paslood/domain/balance_sheet.py` and `BuildPortfolioOverviewUseCase.consolidate_balance_sheet(repo, db)` in `src/paslood/use_cases/build_overview.py` to centralize asset exclusion and balance sheet consolidation across Web and CLI.
  - Added `IngestStatementUseCase` in `src/paslood/use_cases/ingest_statement.py` and `infer_institution_from_account()` in `src/paslood/domain/account.py`.

### Changed
- **Use Case & Adapter Decoupling (#47)**:
  - Removed direct adapter import (`paslood.adapters.ai.base`) and duplicate constants from `AdviseAiUseCase` (`src/paslood/use_cases/advise_ai.py`), exposing public `validate_question()` and `build_prompt()` methods.
  - Simplified `/api/ingest/kbc` and `/api/ingest/bunq` in `src/paslood/delivery/web/routers/ingestion.py` to delegate to `IngestStatementUseCase` without mutating singleton gateway state.
  - Relocated `AuthManager`, `hash_password`, and `verify_password` to `src/paslood/adapters/security/auth_manager.py` with backward-compatible re-exports in `src/paslood/delivery/web/auth.py`.

### Fixed
- **Persistence & Precision Hygiene (#47)**:
  - Injected `SecretVault` into `ConfigRepository` and implemented atomic YAML writes via `_write_yaml_atomic` (`tempfile` + `0o600` permissions + `os.replace`).
  - Applied SQLite WAL pragmas directly on the primary connection in `LocalDbRepository._get_connection()`, eliminating redundant double connection opens per query.
  - Updated `cli.py:advise` to include discovered assets and liabilities from `LocalDbRepository` and converted `enrich_liability_dict` in `src/paslood/delivery/web/helpers.py` to `Decimal` arithmetic.

---

## [0.12.0] - 2026-10-28

### Added
- **Statement Account Prefill & Unmapped Account Upload Prompts (#45)**:
  - Added `LocalDbRepository.get_discovered_account_summaries()` and `GET /api/accounts/discovered` summarizing statement account numbers, transaction counts, and inferred institutions.
  - Added unmapped account quick-add banner and chips in Settings Known Accounts card, allowing one-click prefilling of account number, institution hint, and suggested label.
  - Added HTML `<datalist id="discovered-acc-datalist">` and `onKnownAccNumChanged()` auto-inference in Known Account registration form.
  - Added unmapped account detection during CSV statement ingestion (`/api/ingest/kbc`, `/api/ingest/bunq`), returning `unregistered_accounts` list in response.
  - Added interactive toast prompt on statement upload offering immediate one-click navigation to register newly discovered accounts.

---

## [0.11.0] - 2026-10-28

### Added
- **Known Accounts & Inter-Account Flow Categorization (#43)**:
  - Added `KnownAccount` domain model (`src/paslood/domain/account.py`) supporting user-defined external accounts and custom labels (e.g. Saxo, Bunq, KBC) with account types (`INVESTMENT`, `SAVINGS`, `CHECKING`).
  - Added repository storage in `portfolio.yaml` for known accounts via `ConfigRepository.load_known_accounts()`, `save_known_account()`, and `delete_known_account()`.
  - Added REST endpoints `GET /api/accounts/known`, `POST /api/accounts/known`, and `DELETE /api/accounts/known/{account_id}` under `src/paslood/delivery/web/routers/settings.py`.
  - Added Known Accounts management card and form in Settings UI (`settings_wizard.js` and `index.html`) with interactive registration and deletion.
  - Enhanced transaction categorization (`CategorizeTransactionsUseCase`) to inspect known accounts: automatically categorizes transfers to/from investment accounts (e.g. Saxo) as `INVESTMENTS`, savings accounts (e.g. Bunq Savings, KBC Spaar) as `SAVINGS`, and internal accounts as `TRANSFER`.
  - Enhanced `formatAccountBadge` in `assets_cashflow.js` to cross-reference registered known accounts and display custom user labels (e.g. `Saxo Investor ••9012`).
  - Enhanced `BunqCsvGateway` to calculate net cash balances from transaction statements and register discovered cash assets with true balances, ensuring Bunq accounts are listed and assignable in Holdings & Buckets.

---

## [0.10.0] - 2026-10-28

### Added
- **Multi-Bank Statement & Position Overview Ingestion (#37)**:
  - Added `BunqCsvGateway` (`src/paslood/adapters/ingestion/bunq_csv.py`) supporting Bunq checking and savings CSV exports with European decimal amounts, occurrence-based transaction deduplication, and internal interest/payday recognition.
  - Enhanced `KbcCsvGateway` (`src/paslood/adapters/ingestion/kbc_csv.py`) to parse KBC Credit Card statement CSVs with foreign currency (`MGA`) conversion to EUR, exclusion of internal debt settlement repayments, and support for classic Mac `\r` line endings.
  - Enhanced `GenericCsvGateway` (`src/paslood/adapters/ingestion/generic_csv.py`) to parse KBC Easy Invest / Pension Savings position overviews (`Positie-overzicht`), classifying pension funds to `AssetClass.FIXED_INCOME` and savings accounts to `AssetClass.CASH` with shared IBAN asset identifiers (`kbc-checking-<IBAN>`) to eliminate double-counting.
  - Added `POST /api/ingest/bunq` and content-based auto-detection across ingestion endpoints.
- **Retroactive Categorization Rules & Multi-File Upload Feedback (#38)**:
  - Implemented `LocalDbRepository.apply_rule_to_transactions()` to retroactively update all matching historical transactions in SQLite when re-bucketing an expense with "Remember this rule" checked.
  - Added customizable rule pattern input field to `#rebucket-modal` and supported regex-safe matching for merchants containing `*` characters (`GOOGLE*GOOGLE PLAY`, `NYX*VendingWork`).
  - Added multi-file upload support (`multiple` attribute on `#file-input`) with client-side header peeking in `detectCsvEndpoint()` and rich summary feedback via `showToast()` and the `#upload-status` banner.
- **Cashflow Table Pagination, Multi-Account Badges & Semantic Categories (#39)**:
  - Added full client-side table pagination controls (page size selector: 25 / 50 / 100 / All, First / Prev / Page Indicator / Next / Last buttons, and "Showing X–Y of Z transactions" counter).
  - Added instant search box (`#tx-search-input`) and category filter dropdown (`#tx-category-filter`).
  - Added **Account** column displaying human-friendly badges (`KBC ••2832`, `KBC Card ••9128`, `bunq ••9982`) and dynamic multi-account filter dropdown (`#tx-account-filter`).
  - Serialized `account_id` in `GET /api/overview` and expanded SQLite transaction fetch limit to 10,000 records.
  - Color-coded transaction categories with distinct semantic palettes across all categories and rebuilt precompiled Tailwind stylesheet `styles.css`.
- **Precompiled Tailwind CSS & Toast Confirmation Modals (#32)**:
  - Replaced runtime Tailwind CDN with precompiled static stylesheet `styles.css` built via `npm run build:css`.
  - Implemented non-blocking toast notifications and promise-based confirmation modals.
- **Workspaces Consolidation & Buy Order Tickers (#31)**:
  - Reorganized dashboard tabs into 4 task-focused workspaces (`Overview`, `Strategy`, `Cashflow & Import`, `Settings`).
  - Added responsive bucket cards and automated buy order ticker cards with rebalancing suggestions.
- **Security Hardening, Vault v2 & Decimal Precision (#30)**:
  - Upgraded backup vault to AES-256-GCM v2 with backward-compatible v1 restore.
  - Enforced strict Decimal precision across portfolio and planning domain models and SQLite storage.
- **Clean Architecture Router Modularization (#29)**:
  - Modularized `app.py` into dedicated APIRouters under `src/paslood/delivery/web/routers/`.

### Changed

### Fixed

---

## [0.9.0] - 2026-10-27

### Added
- **Live Bucket Allocation Total Badge**: Added real-time sum indicator badge and batch target update endpoint (`POST /api/buckets/targets`) allowing atomic allocation reallocation.

### Changed

### Fixed
- **Bucket Allocation Balance Enforcement (#25)**: Prevented bucket target weights summing to >100% with domain validation and disabled save action when active buckets are unbalanced.

---

## [0.8.0] - 2026-10-25

### Added
- **Legally Grounded Belgian Fiscal Shield & EquatePlus Forensic Tax Engine**:
  - Added `src/paslood/domain/tax_rules.py` with official Belgian statutory rules and FOD Financiën citations (`WIB 92 Art. 90/101`, `WDRT Art. 120–126/2`, `WIB 92 Art. 19bis`), TOB plafond caps (`0.12%` cap €1,300, `0.35%` cap €1,600, `1.32%` cap €4,000), and ASML's official Dec 31, 2025 Euronext Amsterdam closing price (`€921.40`).
  - Enhanced `OptimizeTaxUseCase` with pre-2026 historical loss protection (`max(benchmark_price, historical_purchase_price)`), 5-year exemption carryover (`+€1,000/yr` up to `€15,000`, doubled for joint filing), Art. 19bis Reynders 30% tax split for funds with `>10%` debt claims, and an inverse **Max Tax-Free Share Trim Solver**.
  - Added `EQUATEPLUS_CH` (Equatex AG Zurich) custodian profile reconciling `0.35%` brokerage commission + `0.15%` Swiss stamp duty (*Zegelrechten*), unwithheld `0.35%` Belgian TOB self-declaration alerts, and historical FMV vs. 31 Dec 2025 fotomoment gain comparison.

### Changed
- **Product Vision & Documentation**:
  - Updated `README.md`, `docs/index.md`, and `docs/guidance/tax-optimization.md` around the **Paslood** Whole-Life Balance Sheet & PDT Strategic Companion vision.

### Fixed

---

## [0.7.0] - 2026-10-25

### Added
- **Legally Grounded Belgian Fiscal Shield & EquatePlus Forensic Tax Engine**:
  - Added `src/paslood/domain/tax_rules.py` with official Belgian statutory rules and FOD Financiën citations (`WIB 92 Art. 90/101`, `WDRT Art. 120–126/2`, `WIB 92 Art. 19bis`), TOB plafond caps (`0.12%` cap €1,300, `0.35%` cap €1,600, `1.32%` cap €4,000), and ASML's official Dec 31, 2025 Euronext Amsterdam closing price (`€921.40`).
  - Enhanced `OptimizeTaxUseCase` with pre-2026 historical loss protection (`max(benchmark_price, historical_purchase_price)`), 5-year exemption carryover (`+€1,000/yr` up to `€15,000`, doubled for joint filing), Art. 19bis Reynders 30% tax split for funds with `>10%` debt claims, and an inverse **Max Tax-Free Share Trim Solver**.
  - Added `EQUATEPLUS_CH` (Equatex AG Zurich) custodian profile reconciling `0.35%` brokerage commission + `0.15%` Swiss stamp duty (*Zegelrechten*), unwithheld `0.35%` Belgian TOB self-declaration alerts, and historical FMV vs. 31 Dec 2025 fotomoment gain comparison.

### Changed
- **Product Vision & Documentation**:
  - Updated `README.md`, `docs/index.md`, and `docs/guidance/tax-optimization.md` around the **Paslood** Whole-Life Balance Sheet & PDT Strategic Companion vision.

### Fixed

---

## [0.6.0] - 2026-10-25

### Added
- **Frontend JS Integrity & Playwright E2E UI Testing**:
  - Added `tests/delivery/test_frontend_integrity.py` to validate JavaScript syntax (`node --check`), static asset serving, inline HTML event handler function bindings, and Node.js unit execution across all frontend modules.
  - Added `tests/e2e/test_ui_workflows.py` and `tests/e2e/conftest.py` using Playwright headless Chromium to verify dashboard data hydration, tab navigation, allocation visualizer toggles, modals, language switching, and theme toggling with strict zero-tolerance listeners for `pageerror`, `console.error`, and local HTTP 4xx/5xx responses.
  - Integrated Frontend JS & Playwright E2E UI tests into `.github/workflows/ci.yml`, `scripts/ci_summary.py`, `AGENTS.md`, and `.agents/skills/issue-worker/SKILL.md`.

### Changed
- **Modularized Frontend JavaScript**:
  - Extracted ~2,545 lines of inline JavaScript from `src/paslood/delivery/web/templates/index.html` into 6 domain-focused static modules under `src/paslood/delivery/web/static/js/` (`core.js`, `dashboard.js`, `buckets.js`, `guidance.js`, `assets_cashflow.js`, `settings_wizard.js`), reducing `index.html` to ~1,750 lines of clean HTML markup.

### Fixed
- **Broken Frontend Navigation & Dashboard Hydration**:
  - Removed an extraneous closing brace `}` after `renderExcludedBuckets` that caused an uncaught `SyntaxError` and aborted script execution in the browser.
  - Added inline SVG favicon links in `index.html` and `login.html` to eliminate `/favicon.ico` 404 console errors.
  - Added defensive `typeof Chart !== 'undefined'` and `typeof marked !== 'undefined'` checks so dashboard data hydration succeeds even if external CDNs are unreachable.

---

## [0.5.0] - 2026-10-25

### Added
- **Frontend JS Integrity & Playwright E2E UI Testing**:
  - Added `tests/delivery/test_frontend_integrity.py` to validate JavaScript syntax (`node --check`), static asset serving, inline HTML event handler function bindings, and Node.js unit execution across all frontend modules.
  - Added `tests/e2e/test_ui_workflows.py` and `tests/e2e/conftest.py` using Playwright headless Chromium to verify dashboard data hydration, tab navigation, allocation visualizer toggles, modals, language switching, and theme toggling with strict zero-tolerance listeners for `pageerror`, `console.error`, and local HTTP 4xx/5xx responses.
  - Integrated Frontend JS & Playwright E2E UI tests into `.github/workflows/ci.yml`, `scripts/ci_summary.py`, `AGENTS.md`, and `.agents/skills/issue-worker/SKILL.md`.

### Changed
- **Modularized Frontend JavaScript**:
  - Extracted ~2,545 lines of inline JavaScript from `src/paslood/delivery/web/templates/index.html` into 6 domain-focused static modules under `src/paslood/delivery/web/static/js/` (`core.js`, `dashboard.js`, `buckets.js`, `guidance.js`, `assets_cashflow.js`, `settings_wizard.js`), reducing `index.html` to ~1,750 lines of clean HTML markup.

### Fixed
- **Broken Frontend Navigation & Dashboard Hydration**:
  - Removed an extraneous closing brace `}` after `renderExcludedBuckets` that caused an uncaught `SyntaxError` and aborted script execution in the browser.
  - Added inline SVG favicon links in `index.html` and `login.html` to eliminate `/favicon.ico` 404 console errors.
  - Added defensive `typeof Chart !== 'undefined'` and `typeof marked !== 'undefined'` checks so dashboard data hydration succeeds even if external CDNs are unreachable.

---

## [0.4.0] - 2026-10-25

### Added
- **CI/CD Job Summaries & Automated Release Pipeline (Issue #15)**:
  - Added structured Markdown job summaries across CI, documentation, and release workflows.
  - Added `scripts/ci_summary.py` helper module supporting summary generation for linting, testing, docs deployment, and release distributions.
  - Enhanced `ci.yml` lint job with breakdown of Ruff linter, Ruff formatter, and MkDocs strict build checks.
  - Enhanced `ci.yml` test job with test execution status, high-level coverage percentage vs. $\ge 90\%$ target threshold, and full Markdown coverage breakdown table via `coverage report --format=markdown`.
  - Added documentation deployment summary in `docs.yml` and release distribution artifact listing in `release.yml`.
  - Added comprehensive unit test suite in `tests/unit/test_ci_summary.py`.
  - Added automated release pipeline in `.github/workflows/release.yml` triggering on push to `main` with unreleased changelog detection, automatic version bumping, and release note extraction via `scripts/release.py`.
  - Added `--version` / `-V` CLI flag (`paslood --version`) and `GET /api/version` endpoint linking code directly to package metadata.
  - Added dynamic app version indicators in the dashboard navigation header and Settings tab.
- **Autonomous Issue Worker Protocol Skill (`issue-worker`)**:
  - Consolidated issue processing lifecycle into a deterministic skill in `.agents/skills/issue-worker/SKILL.md` (Issue #16).
  - Added strict guardrails banning exploratory codebase probing, reading `poll_issues.py` internals, or creating dummy files.
  - Streamlined sidecar worker prompt in `~/.gemini/config/sidecars/paslood-issue-worker/sidecar.json` to reduce token consumption and eliminate workflow meandering.
- **Two-Stage Autonomous Issue Queue & Plan Archiving**:
  - Implemented asynchronous issue poller (`scripts/poll_issues.py`) supporting the deterministic two-stage approval workflow (`agent:plan` -> `agent:plan-review` -> `agent:approved` -> `agent:in-progress` -> `agent:review-ready`) (Issue #2).
  - Automatically commits and pushes architecture plans (`docs/plans/PLAN-<id>-<slug>.md`) to origin feature branches before posting issue review comments, resolving remote 404 links.
  - Added expandable Markdown previews of architecture plans directly within GitHub issue comments for mobile/remote accessibility.
  - Added GitHub Actions workflow (`.github/workflows/issue-worker.yml`) triggered by `issues: [opened, labeled]`, `workflow_dispatch`, and hourly schedule, enabling remote plan generation and lifecycle transitions in the cloud without requiring a local machine to be running.
  - Added persistent architecture plan directory in `docs/plans/` with `README.md` and `PLAN-TEMPLATE.md`.
  - Integrated Architecture Plans into `mkdocs.yml` navigation for built-in documentation and GitHub Pages.
- **Strategic Allocation Visualizer & Bucket Drift Divergence (Issue #13)**:
  - Redesigned bucket allocation visualizer with horizontal bullet meters showing actual vs. target weights.
  - Added drift divergence indicators and visual bounds for rebalancing thresholds.
- **Bucket Exclusion from Rebalancing Calculations (Issue #3)**:
  - Added `include_in_rebalancing` flag on `Bucket` and `BucketAllocationResult` entities.
  - Excluded buckets (e.g. Primary Residence / Real Estate) are omitted from liquid portfolio rebalancing target weights and contribution advice.
  - Excluded buckets display "Excluded from Rebalancing" status badges in the UI without generating drift imbalances.
  - Added checkbox in Add/Edit Bucket modal to toggle rebalancing inclusion.
- **Belgian Multi-Language Internationalization & Dutch Translation (Issue #7)**:
  - Added comprehensive Dutch (NL) translation for all core dashboard sections (Overview, Buckets, Guidance, AI Advisor, Data & Assets, Settings, and Setup Wizard).
  - Added multi-language support framework covering Belgium's official languages: Dutch (`nl`), English (`en`), French (`fr`), and German (`de`).
  - Added fast, accessible language switcher controls to the desktop navigation header, mobile drawer, and a dedicated Language & Localization card in the Settings tab.
  - Added `GET /api/i18n` and `GET /api/i18n/{lang}` endpoints in `src/paslood/delivery/web/app.py`.
  - Added offline-capable client-side internationalization module in `src/paslood/delivery/web/static/i18n.js` with instant local-storage persistence and reactive re-rendering on language switch.
  - Updated `ConfigRepository` to persist language preference across sessions in `portfolio.yaml`.
  - Added test suite in `tests/delivery/test_i18n.py` verifying endpoint contracts and language persistence.
- **Containerized Self-Hosting & Authentication (Issue #11)**:
  - Added multi-stage Docker build with non-root security runner and health check.
  - Implemented session authentication with Google OAuth, GitHub OAuth, and PBKDF2 password authentication modes.
  - Added CLI `set-password` command to initialize or reset master admin credentials.
- **Responsive Mobile UX & Loan Amortization Schedule (Issue #6)**:
  - Added mobile navigation bottom bar and slide-out drawer for seamless smartphone access.
  - Added interactive loan amortization schedule calculator on liability cards.
  - Added light/dark theme toggle with persistent user preference.
- **Encrypted Cloud Backup & Secret Vault (Issue #10)**:
  - Added AES-GCM encrypted backup and restore for portfolio configuration and secret vault.
  - Added cloud folder sync helper for Proton Drive / Google Drive.

### Fixed
- Fixed regional European number and currency formatting across tables, trajectory charts, and milestone cards (Issue #12).
- Hardened server against unauthenticated LAN/external interface binding without configured credentials (Issue #5).
- Resolved Anthropic API model parameter compatibility errors and masked API key overwrite issues (Issue #10).
- Fixed PDT MCP asset sync caching behavior to prevent stale holdings after re-authentication (Issue #10).

---

## [0.3.0] - 2026-10-14

### Added
- **Multi-CSV Upload Accumulation & Local SQLite Storage**:
  - Implemented `LocalDbRepository` in `src/paslood/adapters/repositories/local_db.py` using SQLite.
  - Caches transactions, discovered bank assets, and liabilities permanently without overwriting earlier uploads.
  - Automatically deduplicates overlapping transactions across monthly bank statements using SHA-256 content hashes.
  - Cashflow metrics dynamically aggregate across all stored transactions in the database.
- **Strategic Allocation Bucket Management**:
  - Added interactive **Add Bucket** modal (`#bucket-modal`) with customizable color palettes, target weights, and drift tolerances (`POST /api/buckets`).
  - Added **Edit / Rename Bucket** functionality and modal (`PUT /api/buckets/{id}`) to rename buckets, change targets, or adjust color themes.
  - Added **Delete Bucket** endpoint (`DELETE /api/buckets/{id}`) with graceful unassignment of rules.
  - Added vibrant, distinct color palette (`#3B82F6`, `#10B981`, `#F59E0B`, `#8B5CF6`, `#EC4899`, `#06B6D4`, `#F97316`, `#6366F1`) for all buckets.
- **Holdings Assignment Enhancements**:
  - Filtered out €0,00 holdings from the Portfolio Holdings & Assignment table to focus purely on active assets.
  - Added color-coordinated badges with matching bullet dots for each bucket in the assignment table.
- **Mortgage & Loan Editing**:
  - Added an interactive **Edit** button for each mortgage, loan, or credit line on the dashboard.
  - Preserves user-customized outstanding principal and actual APR across subsequent statement uploads.

### Fixed
- Fixed KBC loan detection: removed hardcoded/synthetic multiplier estimates (`monthly * 240`) and fabricated interest rates (`1.85%`, `9.5%`). Discovered loans default to €0 balance and 0% APR until confirmed and edited by the user.
- Fixed non-functional `+ Add Bucket` button by adding complete modal flow and backend CRUD routes.


---

## [0.2.0] - 2026-10-14

### Added
- **PDT OAuth Auto-Sync & Visual Feedback**:
  - Automatically triggers asset synchronization upon successful OAuth PKCE token exchange.
  - Added celebration banner displaying count of imported holdings and automatically sanitizing callback query parameters.
- **Dynamic AI Model Discovery & Resilience**:
  - Added `GET /api/ai/models` endpoint querying active models (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gpt-4o-mini`, `claude-3-5-haiku-20241022`).
  - Added interactive model selector dropdown with one-click refresh in the AI Advisor tab.
  - Implemented structured error handling to prevent `JSON.parse` crashes when keys are invalid or quotas are exceeded.
- **Balance Sheet: Real Estate Assets & Debt Tracking**:
  - Added `save_manual_asset`, `delete_manual_asset`, `save_manual_liability`, and `delete_manual_liability` to `ConfigRepository`.
  - Added REST endpoints: `POST /api/assets/manual`, `DELETE /api/assets/manual/{id}`, `POST /api/liabilities/manual`, `DELETE /api/liabilities/manual/{id}`.
  - Added dedicated UI cards and interactive modals for Real Estate / Manual Assets and Mortgages / Debts on the Overview dashboard.
- **Portfolio Holdings & Strategic Bucket Mapping**:
  - Added `assign_asset_to_bucket` and endpoint `POST /api/buckets/assign-asset`.
  - Added an interactive holdings mapping table in the Buckets tab allowing users to reassign any PDT, CSV, or manual holding to any bucket with instant drift recalculation.
- **Interactive Projections & Milestones**:
  - Added timeframe selector buttons (`5Y`, `10Y`, `20Y`, `30Y`) and editable CAGR % input to the compound wealth chart.
  - Added Financial Independence Milestones progress bar ladder and custom target modal (`GET /api/milestones`, `POST /api/milestones`).
- **Developer Experience & Containerization**:
  - Added `.devcontainer/devcontainer.json` for VSCode Remote Containers and GitHub Codespaces.
  - Added comprehensive `AGENTS.md` guide for automated coding agents and contributors.
  - Added `CONTRIBUTING.md` and GitHub Copilot instruction files.

### Fixed
- Fixed PDT OAuth client authentication failure by dynamically registering redirect URI variants (`127.0.0.1` and `localhost`).
- Fixed Gemini API model URL formatting by stripping redundant `models/` prefix.

---

## [0.1.0] - 2026-10-14

### Added
- **Clean Architecture Core**:
  - Pure domain models: `Asset`, `Liability`, `Bucket`, `Money`, `BalanceSheet`, `AdviceItem`.
  - Pure use cases: `CalculateBucketAllocationUseCase`, `OptimizeTaxUseCase`, `AdviseDebtPayoffUseCase`, `AdviseContributionUseCase`, `ProjectNetWorthUseCase`, `CategorizeTransactionsUseCase`, `AdviseAiUseCase`.
- **Data Ingestion Gateways**:
  - `KbcCsvGateway`: Bank export statement parser with rule-based transaction classification.
  - `GenericCsvGateway`: Standard CSV asset portfolio parser and template generator.
  - `PdtMcpGateway`: Model Context Protocol integration for Portfolio Dividend Tracker.
  - `PdtAuthManager`: OAuth2 PKCE handshake with dynamic client registration.
- **Belgian 2026 Capital Gains Tax Engine**:
  - Pre-2026 benchmark cost basis (Dec 31, 2025) and post-2025 actual purchase price accounting.
  - Annual €10,000 exemption tracking with 10% tax rate above exemption.
  - PDT time travel price lookup integration.
- **Delivery Layers**:
  - FastAPI asynchronous web dashboard with TailwindCSS, Chart.js, and Jinja2 templates.
  - Typer and Rich/Textual CLI for headless status checking.
  - Interactive onboarding setup wizard.
- **Documentation**:
  - MkDocs Material documentation site built and bundled locally for offline access.

---

[Unreleased]: https://github.com/tiwu/paslood/compare/v0.12.0...HEAD
[0.12.0]: https://github.com/tiwu/paslood/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/tiwu/paslood/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/tiwu/paslood/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/tiwu/paslood/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/tiwu/paslood/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/tiwu/paslood/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/tiwu/paslood/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tiwu/paslood/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tiwu/paslood/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tiwu/paslood/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/tiwu/paslood/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tiwu/paslood/releases/tag/v0.1.0
