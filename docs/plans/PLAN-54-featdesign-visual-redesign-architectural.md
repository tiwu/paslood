# Architecture Plan: [Issue #54] Visual Redesign, Refactoring UI Design System & Brand Metaphor Alignment

- **Issue**: [#54](https://github.com/tiwu/paslood/issues/54)
- **Status**: Completed
- **Author**: Senior UI/UX Designer & Systems Engineer
- **Date**: 2026-10-29
- **Target Branch**: `feature/issue-54-featdesign-visual-redesign-architectural`
- **Design Framework**: *Refactoring UI* (Wathan & Schoger) + Architectural Plumb-Line (*Paslood*) Identity

---

## 0. Refactoring UI Quick Diagnostic & Scoring Audit

**Core Principle**: *Design in grayscale first. Add color last.* Hierarchy must be established through constrained scales of spacing, contrast, and typography before introducing semantic or brand color.

### Baseline Score: **2/10** (1.5 of 8 diagnostic checks satisfied → `round(1.5 / 8 × 10) = 2`)
### Target Score: **10/10** (8 of 8 diagnostic checks satisfied)

| # | Diagnostic Check | Current Status | Codebase Evidence (`index.html` / `input.css` / `*.js`) | Fix to Reach 10/10 |
| :- | :--- | :--- | :--- | :--- |
| **1** | **Does hierarchy read when squinting (blur test)?** | ❌ **FAIL** | `#tab-buckets` toolbar renders 4 competing saturated buttons (`bg-indigo-600`, `bg-blue-600`, `bg-rose-600`, `bg-emerald-600`); colorful OS emojis (`📊`, `🪣`, `🧭`, `💳`, `🎯`, `🚀`) compete with headings. | Enforce **one primary button per view** (Brass/Cobalt filled); demote secondary actions to outlined/muted (`pas-btn-secondary`) and tertiary actions to text-only. Replace emojis with monochrome 1.5px stroke SVGs. |
| **2** | **Does it work in grayscale?** | ❌ **FAIL** | `#kpi-surplus` relies on green (`text-emerald-400`) for emphasis; chart series in `dashboard.js` rely on saturated R/G/B hues; status badges rely on color alone. | Establish grayscale hierarchy via size (`text-3xl`), weight (`font-bold`), and surface luminance first. Differentiate chart lines by stroke width + dash pattern (`solid`, `dashed [6,4]`, `dotted [2,3]`) + direct labels. |
| **3** | **Is there enough white space?** | ❌ **FAIL** | Cards use cramped `p-5` (20px) padding with tight `gap-1.5` (6px) clusters; top filter banner spans full width above KPIs; tables have `pb-2` (8px) cramped cells. | Upgrade card padding to `p-6` (24px), section gaps to `gap-6` (24px) / `space-y-8` (32px), and table cells to `py-3 px-4` (12px/16px). |
| **4** | **Are labels de-emphasized vs. values?** | ⚠️ **PARTIAL** | KPI values are `text-2xl`, but table headers (`<thead class="text-slate-400">`) use normal case and left-align currency columns (`th_value`); form labels compete with inputs. | Style all metric labels & table headers as `text-xs font-semibold uppercase tracking-wider text-pas-tertiary`; right-align all numeric/currency columns (`text-right font-mono tabular-nums`). |
| **5** | **Does spacing follow a consistent scale?** | ❌ **FAIL** | Widespread arbitrary/off-scale values: `p-5` (20px), `px-2.5` (10px), `py-1.5` (6px), `gap-1.5` (6px), `space-y-2.5` (10px), and invalid Tailwind `py-0.2` (line 288). | Restrict layout & component spacing strictly to the Refactoring UI scale: **4, 8, 16, 24, 32, 48, 64px** (`p-1`, `p-2`, `p-4`, `p-6`, `p-8`, `p-12`, `p-16` and matching `gap-*`). |
| **6** | **Is text width constrained?** | ❌ **FAIL** | AI Advisor markdown output (`#ai-response-content`), guidance cards, and setup descriptions stretch across the full `max-w-7xl` (1280px) container (>140ch per line). | Constrain all reading prose, AI analysis, and descriptive subtext to `max-w-prose` (**65ch**, ~45–75 characters) and modal forms to `max-w-md` / `max-w-lg` (448–512px). |
| **7** | **Do colors have sufficient contrast?** | ❌ **FAIL** | **Light mode**: Sankey SVG text is `#f8fafc` on `#ffffff` (**1.04:1**), bucket target pin is `#ffffff` on light gray (**1.1:1**). **Dark mode**: `text-slate-500` (`#64748b`) on `#0f172a` is **3.75:1** (< 4.5:1 AA). | Guarantee WCAG 2.1 AA across both themes: ≥ **4.5:1** for normal text, ≥ **3:1** for large text & UI graphics. Bind SVG/Canvas colors to theme tokens via `getChartThemeTokens()`. |
| **8** | **Are shadows appropriate for elevation?** | ❌ **FAIL** | Dark mode relies on drop shadows (invisible on dark backgrounds) instead of lighter surface steps; light mode applies a single `!important` shadow to all `.bg-slate-900` nodes. | Implement a two-part architectural shadow scale (`sm`, `md`, `lg`, `xl`) in light mode, and **elevation-by-lightness** (`#0B111E` → `#131C2E` → `#23314E` + 1px top highlight) in dark mode. |

---

## 1. Brand Alignment & Metaphorical Architecture ("Paslood")

### 1.1 Conceptual Shift: From Cockpit Telemetry to Plumb-Line Precision
- **Legacy ("Wealth Pilot")**: Aviation cockpits, magnetic compasses (`🧭`), flight trajectories, radar telemetry.
- **Redesigned ("Paslood")**: Named after the builder's **plumb line / lead bob** (*in het lood staan* — standing in true vertical alignment).
  - **Plumb Line (Datum)**: Strategic target allocation (`0.0%` drift).
  - **Gravity / Deflection**: Market drift pulling buckets off-plumb.
  - **Counterweight**: Buy-only monthly savings restoring structural equilibrium.
  - **Foundations & Loads**: Assets are load-bearing columns; liabilities are structural loads; net worth is structural clearance.

### 1.2 Minimalist Architectural Drafting Details (Non-Cluttering)
1. **Subtle 24px Cartesian Drafting Grid (`--pas-bg-grid`)**:
   - Applied to `body` background using `24px` (on the 4/8/16/24/32/48/64 scale) repeating linear gradients at `3%` opacity in light mode and `3.5%` in dark mode.
2. **Corner Registration Marks (`+`)**:
   - Subtle monospace `+` crosshairs positioned at `8px` (`top-2 right-2`) on primary balance-sheet cards at `40%` border opacity.
3. **Dimension & Tolerance Callouts**:
   - Allocation tolerance bands formatted as architectural dimension spans: `├─ ±2.5% ─┤` and `DATUM 0.0%`.

### 1.3 Iconography & Motif Replacement Matrix
Every emoji in navigation, headers, cards, and modals is replaced with consistent **1.5px stroke geometric SVG icons** sized proportionally to adjacent text (`w-4 h-4` [16px] for 12–14px text; `w-5 h-5` [20px] for 16px text; `w-6 h-6` [24px] for 18–20px headings):

| Location (`index.html` / `manifest.json`) | Legacy Motif | New Architectural SVG Icon | Sizing & Pairing Rule |
| :--- | :--- | :--- | :--- |
| **Brand Mark & Favicon** (`#header`, `login.html`, `manifest.json`) | `🧭` / `compass.svg` | **Custom Plumb Bob SVG** (suspended lead weight over vertical datum) | `w-5 h-5` inside `w-8 h-8` (`32px`) badge; `gap-2` (`8px`) to title |
| **Nav 1: Overview** (`#nav-overview`, `#mnav-overview`) | `📊 Overview` | **Floorplan / Layers SVG** (`LayoutGrid`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) + `12px` label |
| **Nav 2: Portfolio & Buckets** (`#nav-portfolio`, `#mnav-portfolio`) | `🪣 Portfolio` | **Structural Columns SVG** (`Columns3`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) + `12px` label |
| **Nav 3: Plan & Rebalance** (`#nav-plan`, `#mnav-plan`) | `🧭 Plan` | **Plumb Scale / Caliper SVG** (`Scale`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) + `12px` label |
| **Nav 4: Cashflow & Import** (`#nav-cashflow`, `#mnav-cashflow`) | `💳 Cashflow` | **Conduit Flow SVG** (`ArrowDownUp`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) + `12px` label |
| **Nav 5: Settings** (`#nav-settings`, `#mnav-settings`) | `⚙️ Settings` | **Calibration Sliders SVG** (`SlidersHorizontal`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) + `12px` label |
| **Setup Wizard CTA** (`openSetupWizard()`) | `🚀 Setup` | **Drafting Ruler / Square SVG** (`Ruler`) | `w-4 h-4` (`16px`) + `gap-1` (`4px`) |
| **Docs Link** (`/guide/index.html`) | `📖 Docs` | **Blueprint Scroll / Sheet SVG** (`FileText`) | `w-4 h-4` (`16px`) + `gap-1` (`4px`) |
| **Milestones Header** (`#milestones-container`) | `🎯 Milestones` | **Elevation Benchmark SVG** (`Flag` / `Milestone`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) |
| **Allocation Mode Toggle** (`#btn-alloc-mode-bullet`) | `🎯` / `⚖️` | **Caliper Bar SVG** / **Plumb Axis SVG** | `w-4 h-4` (`16px`) + `gap-1` (`4px`) |
| **AI Advisor Header** | `🤖 AI Advisor` | **Precision Compass / Spark SVG** (`Sparkles`) | `w-4 h-4` (`16px`) + `gap-2` (`8px`) |

---

## 2. The 7 Refactoring UI Principles Applied to Paslood

### Principle 1: Visual Hierarchy (Grayscale First)
1. **Combine Levers, Don't Multiply**:
   - **KPI Values** (`#kpi-net-worth`, `#kpi-total-assets`, `#kpi-total-debts`, `#kpi-surplus`): Large (`text-3xl` / `30px`), bold (`font-bold`), primary ink (`--pas-text-primary`), `font-mono tabular-nums`.
   - **Labels & Table Headers**: Small (`text-xs` / `12px`), uppercase (`uppercase`), tracked out (`tracking-wider`), medium-semibold (`font-semibold`), muted (`--pas-text-tertiary`).
2. **Strict Button Hierarchy (One Primary Action Per View)**:
   - **Primary (`pas-btn-primary`)**: Filled high-contrast background (`--pas-accent-cobalt` in light, `--pas-accent-brass` or `--pas-accent-cobalt` in dark).
   - **Secondary (`pas-btn-secondary`)**: Outlined (`1px solid var(--pas-border-strong)`), surface background (`--pas-bg-surface`), primary text (`--pas-text-primary`), `shadow-sm`.
   - **Tertiary (`pas-btn-tertiary`)**: Text-only with subtle hover background.

### Principle 2: Constrained Spacing & Sizing Scale
1. **Strict Scale Enforcement**:
   - Allowed spacing values: **`4px` (`1`), `8px` (`2`), `16px` (`4`), `24px` (`6`), `32px` (`8`), `48px` (`12`), `64px` (`16`)**.
   - Card paddings upgraded to **`p-6` (24px)**, section gaps to **`gap-6` (24px)** and **`space-y-8` (32px)**.
2. **Width Constraints**:
   - Apply `max-w-prose` (`65ch`) to `#ai-response-content`, advice item descriptions, and onboarding text.
   - Constrain form modals to `max-w-lg` (`512px`).

### Principle 3: Modular Typography Scale (2 Font Families Max)
1. **Font Families**:
   - **UI & Headings (`font-sans`)**: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` with `font-feature-settings: 'cv02' 1, 'cv03' 1, 'cv04' 1`.
   - **Numbers, Tickers & Codes (`font-mono`)**: `'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace` with `font-variant-numeric: tabular-nums`.
2. **Hand-Tuned Modular Type Scale**: `12px`, `14px`, `16px`, `18px`, `20px`, `24px`, `30px`.

### Principle 4: Systematic Color Palettes

#### A. Light Theme Refresh: "Architectural Vellum" (Warm Stone-Tinted Grays)
- **Canvas (`--pas-bg-canvas`)**: `#F5F3EE` (Vellum 100 — warm drafting paper, zero glare)
- **Elevated Surface / Card (`--pas-bg-surface`)**: `#FDFCFA` (Vellum 50 — soft warm ivory)
- **Inset Well / Table Header (`--pas-bg-surface-inset`)**: `#EBE7DF` (Vellum 200 — recessed stone well)
- **Subtle Border (`--pas-border-subtle`)**: `#DFDBD2` (Vellum 300)
- **Strong Border (`--pas-border-strong`)**: `#C8C2B6` (Vellum 400)
- **Primary Text (`--pas-text-primary`)**: `#1C1917` (Stone 900 — **15.8:1** contrast)
- **Secondary Text (`--pas-text-secondary`)**: `#44403C` (Stone 700 — **8.9:1** contrast)
- **Tertiary Text (`--pas-text-tertiary`)**: `#57534E` (Stone 600 — **6.3:1** contrast, passes AA for 12px text)

#### B. Dark Theme Optimization: "Midnight Blueprint" (No Halation, Elevation by Lightness)
- **Canvas (`--pas-bg-canvas`)**: `#0B111E` (Blueprint 950)
- **Inset Well (`--pas-bg-surface-inset`)**: `#080C16`
- **Card Surface (`--pas-bg-surface`)**: `#131C2E` (Blueprint 900 — Level 1 elevated surface)
- **Hover / Input Surface (`--pas-bg-surface-muted`)**: `#1C2840` (Blueprint 800 — Level 2 interactive surface)
- **Modal / Floating Surface (`--pas-bg-surface-elevated`)**: `#23314E` (Blueprint 750 — Level 3 modal overlay)
- **Subtle Border (`--pas-border-subtle`)**: `#23314E` + `1px` top highlight `rgba(255, 255, 255, 0.06)`
- **Strong Border (`--pas-border-strong`)**: `#33476B` (Blueprint 700)
- **Primary Text (`--pas-text-primary`)**: `#F1F5F9` (95% off-white chalk — **14.2:1** contrast)
- **Secondary Text (`--pas-text-secondary`)**: `#CBD5E1` (**10.1:1** contrast)
- **Tertiary Text (`--pas-text-tertiary`)**: `#94A3B8` (**5.6:1** contrast on `#131C2E`)
- **Warm Optimism Accent (`--pas-accent-brass`)**: `#F59E0B` / `#FBBF24` (Plumb Bob Brass)

### Principle 5: Depth, Shadows & Border Radius System
- **Constrained Border Radius System**: `rounded-sm` (`2px`), `rounded` (`4px`), `rounded-md` (`6px`), `rounded-lg` (`8px`).
- **Two-Part Shadow Scale (Light Mode) vs. Lightness + Rim (Dark Mode)**: Cards in dark mode use surface lightness steps (`#0B111E` → `#131C2E` → `#23314E`) plus a subtle `1px` top specular highlight.

### Principle 6: Data Visualization & Table Rigor
- **Colorblind-Safe, Desaturated Architectural Chart Palette**:
  - Net Worth: `#1E4E79` (Light Cobalt) / `#38BDF8` (Dark Cyan) — Solid `2.5px` (Historical), Dashed `[4,4]` (Projected)
  - Total Assets: `#1F6F5B` (Light Patina) / `#34D399` (Dark Mint) — Dashed `[6,4]`
  - Total Debts: `#9A3412` (Light Oxide) / `#FB923C` (Dark Terracotta) — Dotted `[2,3]`
  - Plumb Target Datum: `#1C1917` (Light Charcoal Caliper) / `#FBBF24` (Dark Brass Caliper)
- **Table Design Rules**: Right-align all numerical columns (`text-right font-mono tabular-nums`), left-align text columns, horizontal dividers only, generous `py-3 px-4` cell padding.

### Principle 7: Layout, Composition & Accessibility
- Left-aligned scannability across cards and tables; `max-w-prose` (`65ch`) on reading prose.
- Explicit `:focus-visible` ring (`2px solid var(--pas-accent-brass)`) and `@media (prefers-reduced-motion: reduce)`.

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
        │   │   ├── input.css          # Semantic CSS tokens (--pas-*), Refactoring UI scales & drafting grid
        │   │   └── styles.css         # Precompiled Tailwind stylesheet
        │   ├── js/
        │   │   ├── core.js            # Theme resolver (getChartThemeTokens), architectural palette
        │   │   ├── dashboard.js       # Chart.js theme binding (donut & trajectory)
        │   │   ├── buckets.js         # Plumb-line rebalancing caliper & target datum
        │   │   ├── guidance.js        # Polished advice cards with registration ticks
        │   │   └── assets_cashflow.js # Dynamic Sankey SVG text fill & spending chart colors
        │   ├── locales/               # Updated strings (sunset aviation telemetry terms)
        │   └── manifest.json          # Plumb bob icon SVG path replacing compass
        └── templates/
            ├── index.html             # Clean SVG iconography, Refactoring UI spacing/hierarchy
            └── login.html             # Matching Plumb Bob mark & theme tokens
```

---

## 4. Verification & Rollout Checklist

- [x] Architecture plan synchronized in branch and GitHub Issue #54
- [x] Frontend integrity & E2E tests written first (Red → Green)
- [x] Linters pass: `uv run ruff check src tests`
- [x] Formatting passes: `uv run ruff format --check src tests`
- [x] Documentation builds: `uv run mkdocs build --strict`
- [x] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [x] PR submitted linking Issue #54 and this plan
