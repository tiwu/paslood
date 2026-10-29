# Architecture Plan: [Issue #47] Align Clean Architecture Ports, Use Cases, and Adapter Hygiene

- **Issue**: [#47](https://github.com/tiwu/paslood/issues/47)
- **Status**: Completed
- **Author**: Autonomous Agent / Contributor
- **Date**: 2026-10-29
- **Target Branch**: `feature/issue-47-align-clean-architecture-ports-use-cases`

---

## 1. Problem Statement & Motivation

An architectural review of Paslood against Clean Architecture (Hexagonal / Ports & Adapters) principles identified 7 targeted boundary and contract alignment gaps:

1. **CA-01 (High)**: `use_cases/advise_ai.py` imports `BaseAIAdvisorClient` directly from `paslood.adapters.ai.base`, defines duplicate `MAX_QUESTION_LENGTH` and `_INJECTION_PATTERNS` constants, and `delivery/web/routers/ai.py` calls private methods (`_validate_question`, `_build_prompt`) while passing `ai_client=None` (`# type: ignore`).
2. **CA-02 (High)**: `PortfolioRepository` and `TransactionRepository` protocols in `use_cases/ports.py` have drifted from `ConfigRepository` and `LocalDbRepository` method signatures.
3. **CA-03 (High)**: Balance sheet consolidation (`get_consolidated_balance_sheet`) and `exclude_property` / `include_in_net_worth` asset filtering are duplicated across `delivery/web/helpers.py`, `routers/planning.py`, `use_cases/build_overview.py`, and `cli.py` (where `cli.py:advise` omits discovered assets/liabilities).
4. **CA-04 (Medium)**: `delivery/web/routers/ingestion.py` duplicates KBC and Bunq CSV ingestion workflows, mutates shared singleton gateway `categorizer` state per request, and calls private `LocalDbRepository._infer_institution_from_account`.
5. **CA-05 (Medium)**: `enrich_liability_dict` in `delivery/web/helpers.py` duplicates loan amortization fallback using `float` arithmetic instead of `Decimal`.
6. **CA-06 (Medium)**: `ConfigRepository.load_settings()` instantiates `AppSettings.from_env()` inline instead of accepting an injected `SecretVault`, writes YAML files non-atomically, and `LocalDbRepository._get_connection()` opens a redundant second SQLite connection per query for WAL pragmas.
7. **CA-07 (Low)**: SQLite-backed `AuthManager` and password hashing live in `delivery/web/auth.py` and are imported by `cli.py:set_password`.

---

## 2. Requirements & Acceptance Criteria

- [x] `src/paslood/use_cases/` has zero imports from `paslood.adapters` or `paslood.delivery`
- [x] `AIAdvisorPort`, `PortfolioRepository`, and `TransactionRepository` in `src/paslood/use_cases/ports.py` are `@runtime_checkable` and verified against concrete adapters (`ConfigRepository`, `LocalDbRepository`, `BaseAIAdvisorClient`)
- [x] `BalanceSheet.with_effective_assets(buckets, exclude_property)` and `BuildPortfolioOverviewUseCase.consolidate_balance_sheet(repo, db)` centralize asset filtering and balance sheet consolidation across Web and CLI
- [x] `IngestStatementUseCase` and `infer_institution_from_account` replace duplicated ingestion route orchestration and singleton mutation
- [x] `ConfigRepository` supports injected `SecretVault` and atomic YAML writes (`_write_yaml_atomic`); `LocalDbRepository` sets WAL pragmas on the primary connection; `AuthManager` lives in `adapters/security/auth_manager.py` with backward-compatible re-exports in `delivery/web/auth.py`
- [x] Automated tests cover all cases with $\ge 90\%$ test coverage

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/paslood/domain/`)
- `BalanceSheet.with_effective_assets(buckets, exclude_property)` in `domain/balance_sheet.py` filters out `REAL_ESTATE` assets and assets assigned to buckets with `include_in_net_worth=False` when `exclude_property=True`.
- `infer_institution_from_account(account_id: str) -> str` in `domain/account.py` provides pure domain institution inference from account numbers/IBANs.

### 3.2 Use Cases Layer (`src/paslood/use_cases/`)
- `AIAdvisorPort(Protocol)`, `PortfolioRepository(Protocol)`, and `TransactionRepository(Protocol)` in `use_cases/ports.py` decorated with `@runtime_checkable` and aligned with concrete adapter signatures.
- `AdviseAiUseCase` in `use_cases/advise_ai.py` depends on `AIAdvisorPort | None = None`, exposes public `validate_question()` and `build_prompt()` methods, and eliminates duplicate constants.
- `BuildPortfolioOverviewUseCase.consolidate_balance_sheet(repo, db)` in `use_cases/build_overview.py` consolidates manual and discovered assets/liabilities.
- `IngestStatementUseCase` in `use_cases/ingest_statement.py` orchestrates CSV statement parsing, transaction categorization, persistence, and unregistered account discovery without mutating shared gateway singletons.

### 3.3 Adapters & Repositories (`src/paslood/adapters/`)
- `ConfigRepository` in `adapters/repositories/config_repo.py` accepts optional `secret_vault: SecretVault | None = None` and writes YAML atomically via `_write_yaml_atomic()` (`tempfile` + `0o600` permissions + `os.replace`).
- `LocalDbRepository` in `adapters/repositories/local_db.py` sets `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` directly on the primary connection and delegates `_infer_institution_from_account` to `domain/account.py`.
- `AuthManager`, `hash_password`, and `verify_password` moved to `adapters/security/auth_manager.py`.

### 3.4 Delivery Frameworks (`src/paslood/delivery/`)
- `delivery/web/routers/ai.py` calls public `AdviseAiUseCase.build_prompt()` and `execute()`.
- `delivery/web/routers/ingestion.py` delegates KBC and Bunq uploads to `IngestStatementUseCase`.
- `delivery/web/routers/planning.py` and `cli.py` reuse `consolidate_balance_sheet()` and `BalanceSheet.with_effective_assets()`.
- `delivery/web/helpers.py` uses `Decimal` arithmetic in `enrich_liability_dict()` and delegates `get_consolidated_balance_sheet()`.
- `delivery/web/auth.py` re-exports `AuthManager`, `hash_password`, and `verify_password` for backward compatibility.

---

## 4. Test-Driven Development (TDD) Plan

1. **Red (Tests First)**:
   - Layer import boundary test ensuring `use_cases/` never imports `adapters/` or `delivery/`.
   - Port conformance tests (`isinstance` and signature verification) for `PortfolioRepository`, `TransactionRepository`, and `AIAdvisorPort`.
   - Unit tests for `BalanceSheet.with_effective_assets`, `BuildPortfolioOverviewUseCase.consolidate_balance_sheet`, `infer_institution_from_account`, `IngestStatementUseCase`, `ConfigRepository` injected `SecretVault` decryption, and atomic YAML writes.
2. **Green (Implementation)**:
   - Implement each boundary improvement across `domain/`, `use_cases/`, `adapters/`, and `delivery/` while maintaining backward-compatible aliases/re-exports.
3. **Refactor & Quality**:
   - Zero lint errors (`uv run ruff check src tests`)
   - Format check (`uv run ruff format --check src tests`)
   - 90%+ coverage (`uv run pytest --cov=src/paslood --cov-fail-under=90`)

---

## 5. Verification & Rollout Checklist

- [x] Linters pass: `uv run ruff check src tests`
- [x] Formatting passes: `uv run ruff format --check src tests`
- [x] Documentation builds: `uv run mkdocs build --strict`
- [x] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [x] `CHANGELOG.md` updated under `[Unreleased]`
- [x] PR submitted with `Closes #47` and plan linked
