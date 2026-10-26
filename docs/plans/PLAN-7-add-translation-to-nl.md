# Architecture Plan: [Issue #7] Full UI Localization & Per-Language Translation Files

- **Issue**: [#7](https://github.com/tiwu/paslood/issues/7)
- **Status**: Completed (Phase 2 — Full Page Content & Isolated Locale Files)
- **Author**: Autonomous Issue Worker
- **Date**: 2026-10-25
- **Target Branch**: `feature/issue-7-add-translation-to-nl`

---

## 1. Review of Initial Implementation (PR #8 Feedback)
During local verification of PR #8, the following gaps were identified:
1. **Incomplete DOM Coverage**: Only the top navigation bar (`#nav-*`, `#mnav-*`) and the Settings language card had `data-i18n` attributes. Nearly all body content across the 6 main tabs (`Overview`, `Buckets`, `Guidance`, `Data & Assets`, `AI Advisor`, `Settings`) and 7 modals (`Setup Wizard`, `Help`, `Add Asset`, `Add Liability`, `Bucket`, `Milestones`, `Re-Bucket`) remained hardcoded in English.
2. **Untranslated Dynamic JavaScript Renderers**: Client-side renderers (`renderDashboard`, `renderDonutChart`, `renderProjectionChart`, `renderBuckets`, `renderHoldingsMapping`, `renderAdvice`, `recalculateContribution`, `renderTransactions`, `renderMilestones`, `renderManualAssetsAndDebts`, `loadSettings`, `runTaxSimulation`) injected hardcoded English strings and backend `AdviceItem` text without localization.
3. **Inline Dictionaries Instead of Isolated Translation Files**: Translation dictionaries were embedded directly inside `i18n.py` and `i18n.js` rather than isolated into standalone, maintainable per-language resource files.

---

## 2. Architecture Plan: Isolated Locale Files & Complete Page Wiring

### 2.1 File Isolation Structure (Single Source of Truth)
All translatable strings are isolated into dedicated JSON locale files under `src/wealth_pilot/delivery/web/static/locales/`:

```text
src/wealth_pilot/delivery/web/
├── i18n.py                       # Loads static/locales/{lang}.json dynamically
├── app.py                        # Exposes /api/i18n and /api/i18n/{lang}
├── static/
│   ├── i18n.js                   # Client-side i18n engine (fetches & caches locales, interpolates params)
│   └── locales/
│       ├── en.json               # English (Default / Fallback)
│       ├── nl.json               # Nederlands (Belgian/Flemish market primary target)
│       ├── fr.json               # Français (Belgian French)
│       └── de.json               # Deutsch (Belgian German)
└── templates/
    └── index.html                # Full data-i18n* attributes across all tabs, modals & JS renderers
```

### 2.2 Translation Key Namespace Hierarchy
Each locale file (`en.json`, `nl.json`, `fr.json`, `de.json`) is organized into structured namespaces matching the UI domains:
- `header`: Brand subtitle, badge, OAuth banner.
- `nav`: Desktop and mobile navigation tabs (`explore`, `manage`, `overview`, `buckets`, `guidance`, `ai`, `cashflow`, `settings`, `setup`, `docs`, `help`).
- `dashboard`: Overview filter bar, 4 KPI cards, Allocation & Trajectory charts, Milestones tracker, Immediate Recommendations card, and dynamic chart/KPI strings.
- `buckets`: Strategic Buckets header, table columns, Allocation Visualizer, Holdings Mapping table, status badges (`Balanced`, `Underweight`, `Overweight`, `Excluded`), and empty states.
- `guidance`: Buy-Only Rebalancing Calculator, Consolidated Debt Payoff & Action Plan, Belgian 2026 Capital Gains Tax Simulator (inputs, lots breakdown, result cards), and dynamic order/tax statuses.
- `cashflow`: Data Management header, Manual Assets card & table, Liabilities/Mortgages card & table, CSV Ingestion dropzone, Recent Transactions table.
- `ai`: AI Strategic Advisor header, quick strategy prompt chips (both button labels and prompt payloads), custom question input, loading/empty states.
- `settings`: PDT MCP card, Custom MCP Servers card & form, AI Advisor Configuration card & setup guide, Regional Tax & Benchmark card, Language & Localization card.
- `modals`:
  - `rebucket`: Re-bucket transaction modal & category labels.
  - `asset`: Add Manual Asset modal, categories & placeholders.
  - `liability`: Add/Edit Mortgage & Loan modal, loan types, and amortization schedule estimator.
  - `bucket`: Add/Edit Strategic Bucket modal & checkboxes.
  - `milestones`: Configure Wealth Milestones modal.
  - `help`: In-App Help Guide modal.
  - `wizard`: 3-step Interactive First-Time Setup Wizard.
- `advice_items`: Pattern-based localization templates for dynamic `AdviceItem` entries (`Debt-Free Status`, `Priority Debt Payoff`, `Maintain Minimums`, `Underweight`).
- `priority`: Priority badge translations (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`).
- `common`: Shared buttons, statuses, and actions (`Save`, `Cancel`, `Delete`, `Edit`, `Close`, `Light`, `Dark`).

### 2.3 Client-Side Engine (`static/i18n.js`) Capabilities
- **Asynchronous Preloading + Instant Switching**: Fetches `/api/i18n` (or `/static/locales/{lang}.json`) on initialization, caching all locale bundles in memory so switching between `NL`, `EN`, `FR`, and `DE` is instantaneous with zero flicker.
- **Parameter Interpolation**: `I18N.t('dashboard.debt_ratio', { ratio: '12.5' })` replaces `{ratio}` placeholders cleanly.
- **Declarative DOM Attributes**:
  - `data-i18n="key"` for `textContent`
  - `data-i18n-html="key"` for safe static HTML fragments (`<strong>`, `<em>`, `<code>`)
  - `data-i18n-placeholder="key"` for input placeholders
  - `data-i18n-title="key"` for tooltips
- **Dynamic Advice Localization (`I18N.localizeAdvice(adv)`)**: Translates backend-generated `AdviceItem` titles and messages into the active language without polluting pure domain/use-case layers.

---

## 3. Test-Driven Development (TDD) & Verification Plan
1. **Locale File Integrity Tests (`tests/delivery/test_i18n.py`)**:
   - Verify `en.json`, `nl.json`, `fr.json`, and `de.json` exist as standalone JSON files in `src/wealth_pilot/delivery/web/static/locales/`.
   - Assert key parity across all 4 locale files (every section and key present in `en.json` exists in `nl.json`, `fr.json`, and `de.json`).
   - Verify `/static/locales/nl.json` is served directly as a static asset.
   - Verify `index.html` contains `data-i18n` bindings across all 6 tabs and modals.
2. **Quality Gates**:
   - `uv run ruff check src tests`
   - `uv run ruff format --check src tests`
   - `uv run mkdocs build --strict`
   - `uv run pytest -v --cov=src/wealth_pilot --cov-fail-under=90`
