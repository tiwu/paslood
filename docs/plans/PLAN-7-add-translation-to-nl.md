# Architecture Plan: [Issue #7] feat: add translation to NL

- **Issue**: [#7](https://github.com/tiwu/wealth-pilot/issues/7)
- **Status**: Completed
- **Author**: Autonomous Issue Worker
- **Date**: 2026-10-24
- **Target Branch**: `feature/issue-7-add-translation-to-nl`

---

## 1. Problem Statement & Motivation
Wealth Pilot is designed to run locally with complete privacy. While originally drafted with an English user interface, its primary target user base includes Belgian investors managing Belgian-specific financial frameworks (e.g., Belgian 2026 Capital Gains Tax "Meerwaardebelasting", local banks such as KBC, and European macro allocation).

To make the platform accessible, intuitive, and native to the Belgian market, Wealth Pilot requires comprehensive Dutch (Nederlands - NL) internationalization, while also laying the foundation for Belgium's other national languages (French - FR and German - DE), alongside international English (EN).

---

## 2. Requirements & Acceptance Criteria

### Functional Requirements
- **Complete Dutch Translation (NL)**: Comprehensive localization of navigation tabs, overview cards, macro allocation tables, debt payoff guidance, loan amortization simulators, Belgian tax tools, and settings.
- **Belgian Multi-Language Support**: Support for `nl` (Dutch), `en` (English), `fr` (French), and `de` (German).
- **Instant Language Switching in UI**:
  - Accessible language selector dropdown in the desktop header next to the theme toggle.
  - Dedicated language selector in the mobile drawer for phone/tablet users.
  - Dedicated "Language & Localization" card in the Settings tab.
- **Persistence**:
  - Immediate client-side persistence in `localStorage` (`wealth_pilot_language`) to avoid layout flashes on reload.
  - Backend configuration persistence via `ConfigRepository` and `portfolio.yaml` settings (`language: "nl"`).
- **Backend API**:
  - `GET /api/i18n` endpoint providing all available locales, supported languages, and dictionary payloads.
  - `GET /api/i18n/{lang}` endpoint returning locale-specific translation bundles.
  - `POST /api/settings` and `GET /api/settings` updated to support `language`.

### Non-Functional Requirements
- **Local-First & Offline**: Translations bundled in `src/wealth_pilot/delivery/web/static/i18n.js` ensuring 100% offline availability via PWA service workers without external network dependencies.
- **TDD & Coverage**: Automated tests verifying the API endpoints and configuration persistence with $\ge 90\%$ statement coverage.
- **Zero Lint Errors**: Full compliance with `uv run ruff check src tests` and `uv run ruff format --check src tests`.

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- Remains 100% pure Python standard library. No framework or i18n dependencies in domain models.

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- Pure calculation orchestrators continue to return domain entities and typed values without coupling to delivery-specific strings.

### 3.3 Adapters & Repositories (`src/wealth_pilot/adapters/`)
- `ConfigRepository.load_settings()` provides default `"language": "en"` and reads stored user language.
- `ConfigRepository.save_settings()` updates and persists `language` into `portfolio.yaml`.

### 3.4 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- `src/wealth_pilot/delivery/web/i18n.py`: Backend i18n constants (`SUPPORTED_LANGUAGES`, `DEFAULT_LANGUAGE`, `TRANSLATIONS`).
- `src/wealth_pilot/delivery/web/static/i18n.js`: Client-side i18n module with `data-i18n` attribute scanning and reactive event dispatching.
- `src/wealth_pilot/delivery/web/app.py`:
  - `SettingsUpdateRequest` accepts optional `language: str`.
  - Added `GET /api/i18n` and `GET /api/i18n/{lang}` endpoints.
- `src/wealth_pilot/delivery/web/templates/index.html`:
  - Language selector controls in header, mobile drawer, and settings.
  - `data-i18n` attributes on key interface elements.
  - Re-rendering triggers on `languageChanged` events.

---

## 4. Test-Driven Development (TDD) Plan
1. **Red (Tests First)**:
   - Created `tests/delivery/test_i18n.py` verifying `/api/i18n`, `/api/i18n/{lang}`, and `/api/settings` language persistence.
   - Verified initial test failure.
2. **Green (Implementation)**:
   - Implemented `i18n.py`, updated `config_repo.py`, and added endpoints in `app.py`.
   - Wired client-side engine in `i18n.js` and `index.html`.
   - Verified tests pass cleanly.
3. **Refactor & Verification**:
   - Run full pytest test suite with coverage report ($\ge 90\%$).
   - Run `ruff check` and `ruff format`.
   - Build documentation with `mkdocs build --strict`.

---

## 5. Verification Checklist
- [x] Linters pass: `uv run ruff check src tests`
- [x] Formatting passes: `uv run ruff format --check src tests`
- [x] Documentation builds: `uv run mkdocs build --strict`
- [x] Test suite passes with $\ge 90\%$ coverage: `uv run pytest -v --cov=src/wealth_pilot --cov-fail-under=90`
- [x] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR created with `Closes #7`
