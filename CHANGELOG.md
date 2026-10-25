# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Autonomous Issue Worker Protocol Skill (`issue-worker`)**:
  - Consolidated issue processing lifecycle into a deterministic skill in `.agents/skills/issue-worker/SKILL.md`.
  - Added strict guardrails banning exploratory codebase probing, reading `poll_issues.py` internals, or creating dummy files.
  - Streamlined sidecar worker prompt in `~/.gemini/config/sidecars/wealth-pilot-issue-worker/sidecar.json` to reduce token consumption and eliminate workflow meandering.
- **Belgian Multi-Language Internationalization & Dutch Translation (Issue #7)**:
  - Added comprehensive Dutch (NL) translation for all core dashboard sections (Overview, Buckets, Guidance, AI Advisor, Data & Assets, Settings, and Setup Wizard).
  - Added multi-language support framework covering Belgium's official languages: Dutch (`nl`), English (`en`), French (`fr`), and German (`de`).
  - Added fast, accessible language switcher controls to the desktop navigation header, mobile drawer, and a dedicated Language & Localization card in the Settings tab.
  - Added `GET /api/i18n` and `GET /api/i18n/{lang}` endpoints in `src/wealth_pilot/delivery/web/app.py`.
  - Added offline-capable client-side internationalization module in `src/wealth_pilot/delivery/web/static/i18n.js` with instant local-storage persistence and reactive re-rendering on language switch.
  - Updated `ConfigRepository` to persist language preference across sessions in `portfolio.yaml`.
  - Added test suite in `tests/delivery/test_i18n.py` verifying endpoint contracts and language persistence.
- **Bucket Exclusion from Rebalancing Calculations (Issue #3)**:
  - Added `include_in_rebalancing` flag on `Bucket` and `BucketAllocationResult` entities.
  - Excluded buckets (e.g. Primary Residence / Real Estate) are omitted from liquid portfolio rebalancing target weights and contribution advice.
  - Excluded buckets display "Excluded from Rebalancing" status badges in the UI without generating drift imbalances.
  - Added checkbox in Add/Edit Bucket modal to toggle rebalancing inclusion.
- **Remote Architecture Plan Publishing & Cloud Issue Worker**:
  - Automatically commits and pushes architecture plans (`docs/plans/PLAN-<id>-<slug>.md`) to origin feature branches before posting issue review comments, resolving remote 404 links.
  - Added expandable Markdown previews of architecture plans directly within GitHub issue comments for mobile/remote accessibility.
  - Added GitHub Actions workflow (`.github/workflows/issue-worker.yml`) triggered by `issues: [opened, labeled]`, `workflow_dispatch`, and hourly schedule, enabling remote plan generation and lifecycle transitions in the cloud without requiring a local machine to be running.
- **Two-Stage Autonomous Issue Queue**:
  - Implemented asynchronous issue poller (`scripts/poll_issues.py`) supporting the deterministic two-stage approval workflow (`agent:plan` -> `agent:plan-review` -> `agent:approved` -> `agent:in-progress` -> `agent:review-ready`).
  - Added GitHub issue templates for feature requests (`.github/ISSUE_TEMPLATE/feature_request.md`) and bug reports (`.github/ISSUE_TEMPLATE/bug_report.md`).
  - Created standardized `agent:*` label taxonomy in the GitHub repository.
  - Added unit test suite for the issue poller (`tests/unit/test_poll_issues.py`).
- **Architecture & Feature Plan Archive (`docs/plans/`)**:
  - Added persistent architecture plan directory in `docs/plans/` with `README.md` and `PLAN-TEMPLATE.md`.
  - Integrated Architecture Plans into `mkdocs.yml` navigation for built-in documentation and GitHub Pages.
- **Antigravity Scheduled Automation (`wealth-pilot-issue-worker`)**:
  - Configured hourly background automation sidecar (`CRON_TZ=Europe/Brussels 0 * * * *`) for autonomous local queue processing while active.

---

## [0.3.0] - 2026-10-14

### Added
- **Multi-CSV Upload Accumulation & Local SQLite Storage**:
  - Implemented `LocalDbRepository` in `src/wealth_pilot/adapters/repositories/local_db.py` using SQLite.
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
