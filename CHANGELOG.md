# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
