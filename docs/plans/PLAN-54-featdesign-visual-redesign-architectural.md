# Architecture Plan: [Issue #54] Visual Redesign, Architectural Design System & Brand Metaphor Alignment

- **Issue**: [#54](https://github.com/tiwu/paslood/issues/54)
- **Status**: Plan Review
- **Author**: Senior UI/UX Designer & Systems Engineer
- **Date**: 2026-10-29
- **Target Branch**: `feature/issue-54-featdesign-visual-redesign-architectural`

---

## 1. Problem Statement & Motivation

Following the project's recent rebrand from **"Wealth Pilot"** to **"Paslood"** (*Dutch*: plumb line / lead bob, evoking *in het lood staan* — true vertical alignment), the current application still suffers from three major visual, thematic, and accessibility deficits:

1. **Outdated Aviation & Flight Navigation Motifs**:
   - The UI still presents navigation-oriented elements: compass emojis (`🧭`) in the header, favicon, PWA manifest, navigation tabs, mobile bottom bar, and explore banners.
   - Text references like "telemetry & trajectory", "flight guidance", and "autopilot" persist across the English and Dutch locales.
   - The interface is littered with mismatched colorful system emojis (`📊`, `🪣`, `💳`, `⚙️`, `🚀`, `📖`, `🤖`, `🎯`) rather than a cohesive, technical architectural icon language.
2. **Harsh Light-Theme Contrast & Eye Strain**:
   - The current light theme is implemented via 65+ lines of brittle `!important` CSS overrides in `input.css` slapped onto dark Tailwind classes (`.bg-slate-900`, `.text-slate-100`).
   - Saturated, high-contrast lines across data visualizations (screaming emerald `#10b981`, electric blue `#3b82f6`, alarm red `#ef4444`) cause severe optical fatigue during extended financial reviews.
   - Hardcoded dark Chart.js gridlines (`#1e293b`), borders (`#0f172a`), and ticks (`#64748b`) bleed into light mode.
   - In `assets_cashflow.js`, the Sankey SVG hardcodes white text (`fill="#f8fafc"`), making node labels completely invisible in light mode.
   - In `buckets.js`, the target pin marker hardcodes pure white `#ffffff`, making the key strategic allocation target line invisible against light backgrounds.
3. **Flat, Oppressive Dark Mode**:
   - The dark mode relies on generic `#080d1a` / `#0f172a` (Tailwind slate-950/slate-900) and lacks depth, warmth, or visual optimism.
   - It needs elevation into a refined **Midnight Blueprint** aesthetic: deep oceanic blueprint foundations paired with warm "Plumb Bob Brass" accents (`#F59E0B` / `#FBBF24`) that inspire confidence and financial stability.

---

## 2. Requirements & Acceptance Criteria

### 2.1 Brand Alignment & Architectural Metaphor
- [ ] Replace all compass motifs (`🧭`) with custom SVG **Plumb Bob & Line** marks across header, favicon, PWA manifest, and mobile navigation.
- [ ] Incorporate minimalist architectural drafting cues:
  - Subtle 24px Cartesian drafting grid background (`--pas-bg-grid`) at 2.5–4% opacity.
  - Corner registration crosshairs (`+`) and drafting ticks on primary metric cards.
  - Dimension arrows and tolerance guides (`|← 40.0% →|`) for allocation corridors.
- [ ] Replace all informal emojis in navigation buttons, headers, and quick-actions with clean 1.5px-stroke geometric SVG icons (LayoutGrid, Columns3, Scale/DraftingCompass, ArrowDownUp, Sliders, Ruler, Scroll).
- [ ] Update locale files (`en.json`, `nl.json`, `fr.json`, `de.json`) to sunset flight/telemetry jargon in favor of structural balance sheet and alignment terminology.

### 2.2 Light Theme Refresh ("Architectural Vellum")
- [ ] Re-architect the color system around warm drafting vellum:
  - Canvas: `#F7F6F2` (warm organic linen/vellum paper).
  - Surfaces: `#FFFFFF` with warm stone rule borders (`#DDD8CF`).
  - Inset wells: `#EFECE6`.
  - Text: Charcoal ink `#1E232B` (primary), Graphite `#4F5866` (secondary), Stone `#7A8494` (tertiary).
- [ ] Replace brittle `!important` CSS overrides in `input.css` with semantic CSS custom properties (`--pas-*`).
- [ ] Implement a harmonious, desaturated architectural charting palette:
  - Net Worth / Baseline: Blueprint Cobalt (`#2B5C8F`)
  - Assets / Surplus: Architectural Patina (`#2D7A5B`)
  - Liabilities / Debt: Terracotta Brick (`#A84338`)
  - Cash / Buffer: Turned Brass (`#B88628`)
- [ ] Fix light mode SVG text visibility in the Cashflow Sankey diagram (theme-adaptive fill).
- [ ] Fix target pin visibility in `buckets.js` (adaptive plumb-line caliper with dual alignment pointers).

### 2.3 Dark Theme Optimization ("Midnight Blueprint")
- [ ] Establish deep oceanic blueprint undertones:
  - Canvas: Deep Blueprint Slate `#0A0F1A` (HSL 222, 44%, 7%).
  - Surfaces: Elevated Blueprint Navy `#111827` (HSL 220, 38%, 11%) with 1px top specular highlight.
  - Insets: Recessed Telemetry Well `#080D15`.
  - Modals: `#182236`.
- [ ] Introduce warm metallic accents ("Plumb Bob Brass" `#F59E0B` / `#FBBF24`) paired with Blueprint Cyan (`#38BDF8`) and Patina Green (`#34D399`).

### 2.4 Component & Design System Specifications
- [ ] Typography: enforce tabular figures (`tnum`, `cv02`, `cv03`, `cv04`) by default across all financial numbers and monospace alignment for currency and drift percentages.
- [ ] Centralized Chart.js theme resolver in `core.js` (`getChartThemeTokens()`) ensuring donut, trajectory, and monthly spending charts seamlessly re-theme on toggle.
- [ ] Ergonomic mobile bottom navigation bar with 5 equal architectural slots and thumb-friendly touch targets (min 48px).

### 2.5 Verification & Standards
- [ ] Automated tests pass: `uv run pytest tests/delivery/test_frontend_integrity.py tests/e2e/test_ui_workflows.py`.
- [ ] Zero lint/format errors: `uv run ruff check src tests` and `uv run ruff format --check src tests`.
- [ ] Built-in documentation builds strictly: `uv run mkdocs build --strict`.
- [ ] Test coverage maintained $\ge 90\%$.

---

## 3. Hexagonal Architecture & Design System Impact

```text
src/paslood/
├── domain/                  # UNTOUCHED — Pure business rules remain 100% untouched
├── use_cases/               # UNTOUCHED — Pure application orchestrators remain untouched
├── adapters/                # UNTOUCHED — Repositories and ingestion gateways remain untouched
└── delivery/
    └── web/
        ├── static/
        │   ├── css/
        │   │   ├── input.css          # Semantic CSS tokens (--pas-*) & drafting grid
        │   │   └── styles.css         # Precompiled Tailwind stylesheet
        │   ├── js/
        │   │   ├── core.js            # Theme resolver (getChartThemeTokens), SVG plumb mark
        │   │   ├── dashboard.js       # Chart.js theme binding (donut & trajectory)
        │   │   ├── buckets.js         # Plumb-line rebalancing caliper & target datum
        │   │   ├── guidance.js        # Polished advice cards with registration ticks
        │   │   └── assets_cashflow.js # Dynamic Sankey SVG text fill & spending chart colors
        │   ├── locales/               # Updated strings (sunset aviation telemetry terms)
        │   └── manifest.json          # Plumb bob icon SVG path replacing compass
        ├── templates/
        │   └── index.html             # Clean SVG iconography, removed emojis, updated header/nav
        └── app.py                     # Favicon SVG route updating to Plumb Bob
```

---

## 4. Test-Driven Development (TDD) Plan

### 4.1 Red (Tests First)
1. Add regression and contract tests in `tests/delivery/test_frontend_integrity.py`:
   - Assert `manifest.json` no longer references `compass.svg`.
   - Assert `index.html` header, nav, and mobile bar use SVG icons instead of raw emojis.
   - Assert `input.css` contains `--pas-bg-canvas`, `--pas-bg-surface`, `--pas-chart-grid` tokens without brittle `!important` classes.
   - Assert `getChartThemeTokens` exists and is exported/invoked upon theme change.
2. Add Playwright E2E assertions in `tests/e2e/test_ui_workflows.py`:
   - Verify light theme switch applies `--pas-bg-canvas` without visual clipping or unreadable white text.
   - Verify Sankey SVG node text in light mode has contrast $\ge 4.5:1$ against the background.
   - Verify bullet track target datum remains visible and distinct in both light and dark themes.

### 4.2 Green (Implementation)
1. Implement design tokens in `input.css` and recompile `styles.css`.
2. Update `index.html` with clean SVG architecture icons and plumb bob logo.
3. Update `dashboard.js`, `buckets.js`, and `assets_cashflow.js` to consume dynamic theme tokens.
4. Update `manifest.json`, `index.html` favicon, and locale files.

### 4.3 Refactor & Quality
1. Verify `node --check` across all static JS files.
2. Run `uv run ruff check src tests` and `uv run ruff format src tests`.
3. Verify `uv run pytest tests/delivery/test_frontend_integrity.py tests/e2e/test_ui_workflows.py`.
4. Verify `uv run mkdocs build --strict`.

---

## 5. Verification & Rollout Checklist

- [ ] Linters pass: `uv run ruff check src tests`
- [ ] Formatting passes: `uv run ruff format --check src tests`
- [ ] Documentation builds: `uv run mkdocs build --strict`
- [ ] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [ ] Frontend integrity & E2E pass: `uv run pytest tests/delivery/test_frontend_integrity.py tests/e2e/test_ui_workflows.py`
- [ ] PR submitted linking Issue #54 and this plan
