# Architecture Plan — Issue #32: Toast Notifications, Accessible Confirm Dialog & Standalone Precompiled Tailwind CSS

- **Issue**: [#32](https://github.com/tiwu/paslood/issues/32)
- **Status**: Implemented (Review Ready)
- **Author**: Antigravity Assistant
- **Target Release**: v0.9.1

---

## 1. Context & Motivation

Historical review `docs/reviews/UX-REVIEW.md` identified findings **UX-05** and offline PWA reliability limitations:
1. **UX-05 (Browser-Blocking Alert/Confirm Popups)**:
   - Across the frontend, 15 user-facing notifications were triggered via browser-blocking `window.alert()`, and 6 destructive action guards relied on blocking `window.confirm()`.
   - Native dialog popups freeze JavaScript event loops, disrupt browser thread responsiveness, cannot be styled to match Paslood's slate-950 dark theme, and break screen-reader accessibility workflows.
2. **Offline PWA Capability & Elimination of Tailwind Play CDN**:
   - `index.html` relied on runtime script `<script src="https://cdn.tailwindcss.com"></script>` with an inline `tailwind.config` and 90 lines of inline `<style>` overrides.
   - The runtime Play CDN requires live internet access to download and JIT-compile Tailwind classes on every page load, generating console warnings in production and failing entirely when used offline as a local-first PWA.

---

## 2. Architectural Design & Implementation

### 2.1 Non-Blocking Toast Notification System (`core.js`, `index.html`, `styles.css`)
- **Container**: Positioned top-right stackable container `#toast-container` with `aria-live="polite"` and `pointer-events-none` so underlying dashboard widgets remain interactive.
- **API**: `showToast(message, type = 'info', duration = 4000)`:
  - Supported types: `success` (emerald theme with `✓`), `error` (rose theme with `✕`), `warning` (amber theme with `⚠️`), and `info` (blue theme with `ℹ️`).
  - Text content is escaped to prevent injection, and toasts feature smooth opacity/transform transitions.
  - Manual dismiss button with `aria-label="Close notification"` and auto-dismiss timer.
  - Backward compatibility: automatically synchronizes `#settings-notification` if present in the DOM.

### 2.2 Accessible Native Confirmation Dialog Modal (`core.js`, `index.html`)
- **Native Semantic `<dialog>`**: Added `<dialog id="confirmation-dialog">` styled with dark theme cards (`bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl`), scroll containment (`overscroll-behavior: contain`), and dimmed backdrop (`dialog::backdrop` with blur).
- **Promise-Based Interface**: `async function confirmDialog(optionsOrMessage)`:
  - Supports string shorthand or configuration object: `{ title, message, confirmText, cancelText, confirmVariant }`.
  - Variants: `'danger'` (rose button for destructive deletions) and `'primary'` (blue button for rebalancing confirmations).
  - Safe default focus on the Cancel button to prevent accidental destructive confirms on Enter.
  - Keyboard accessibility: pressing Escape dismisses the dialog via `dialog.addEventListener('cancel', ...)` and resolves `false`.
  - Backdrop click dismisses dialog and resolves `false`.
  - Programmatic dismissal via `dialog.close()` does not leak unhandled events to subsequent dialog calls.

### 2.3 Comprehensive Replacement of `alert()` and `confirm()` Calls
Replaced all 15 `alert()` calls and 6 `confirm()` calls across all client-side modules:
- `settings_wizard.js`: PDT disconnect confirm, MCP server deletion confirm, token/URL validation warnings, backup passphrase warnings, cloud sync warnings, wizard 100% allocation balance guard.
- `assets_cashflow.js`: Manual asset delete confirm, loan/liability delete confirm, re-bucket error toast, invalid asset/debt form validation toasts.
- `buckets.js`: Active bucket delete confirm, unbalanced weight warning confirm, bucket validation toasts, target save success toast, target update error toasts.
- `guidance.js`: Empty ticker lookup warning toast.

### 2.4 Standalone Precompiled Tailwind CSS (`tailwind.config.js`, `input.css`, `styles.css`)
- Replaced `<script src="https://cdn.tailwindcss.com"></script>` and 90 lines of inline styles in `index.html` with static `<link rel="stylesheet" href="/static/css/styles.css">`.
- Configured `tailwind.config.js` scanning `templates/**/*.html`, `static/js/**/*.js`, and `static/i18n.js`.
- Created `src/paslood/delivery/web/static/css/input.css` containing Tailwind directives, scrollbar rules, responsive table classes, modal containment, and complete light theme overrides.
- Compiled minified 34KB production stylesheet `styles.css` using `tailwindcss@3`.
- Added `package.json` with `npm run build:css` and `npm run watch:css` scripts for development.

---

## 3. Verification & Test Coverage

1. **Frontend Integrity Suite (`tests/delivery/test_frontend_integrity.py`)**:
   - Verified `cdn.tailwindcss.com` is absent from `index.html` and `/static/css/styles.css` is linked.
   - Tested FastAPI delivery of `/static/css/styles.css` (HTTP 200, Content-Type `text/css`, size > 5KB).
   - Node.js unit tests asserting `showToast` DOM creation, typed classes, and `confirmDialog` Promise resolution.
2. **Playwright E2E UI Tests (`tests/e2e/test_ui_workflows.py`)**:
   - `test_toast_notifications_stacking_and_dismissal`: Verifies toast rendering, typed styling, text content, and close button dismissal.
   - `test_accessible_confirm_dialog_cancel_and_ok`: Verifies promise-based confirmation dialog opens, cancels with `false`, and confirms with `true`.
   - `test_offline_static_css_and_zero_runtime_tailwind_cdn`: Verifies static stylesheet linkage and zero external calls to Tailwind CDN.
3. **Full Regression Suite**:
   - 202/202 pytest test cases passing.
   - 92% code coverage across `src/paslood`.
   - Zero ruff lint/format violations.
   - Strict `mkdocs build --strict` clean build.
