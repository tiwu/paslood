# Architecture Plan: [Issue #25] fix: buckets sum can be >100%

- **Issue**: [#25](https://github.com/tiwu/paslood/issues/25)
- **Status**: Proposed
- **Author**: Autonomous Agent
- **Date**: 2026-10-27
- **Target Branch**: `feature/issue-25-buckets-sum-can-be-100`

---

## 1. Problem Statement & Motivation

On the Strategic Allocation Buckets page (`tab-buckets`), users can edit bucket target allocation weights inline or via the modal. Currently, the interface allows active (rebalancing) bucket weights to sum to more or less than 100% without visual feedback or restriction. 

While the onboarding setup wizard includes a dynamic status badge (`wizard-total-badge`) that validates `total === 100%` before proceeding, the main Buckets page lacks this feedback and allows persisting unbalanced allocations. In an asset allocation and drift calculation engine, target weights must sum to exactly 100% across all rebalanceable buckets to ensure meaningful portfolio drift metrics, buy-only rebalancing advice, and cashflow distribution recommendations.

---

## 2. Requirements & Acceptance Criteria

- [ ] **Live Sum Total Indicator**: The Buckets view displays a prominent total allocation badge that updates in real time as the user edits weights in the table or modals.
- [ ] **Visual Over/Under Feedback**:
  - Exactly 100%: Emerald green badge indicating "Balanced (100%)".
  - Over 100%: Rose/amber badge indicating total percentage and excess (e.g., `110% (+10% Over)`).
  - Under 100%: Amber badge indicating total percentage and deficit (e.g., `90% (-10% Under)`).
- [ ] **Enforce Balanced Persistence**:
  - Target weight modifications in the UI can only be saved when the sum of active rebalanceable buckets equals 100%.
  - Inline input changes update local state and total indicator on `input` events; a dedicated "Save Allocations" action or change handler persists weights only when balanced.
  - The Add/Edit Bucket modal calculates projected total weight and blocks saving if unbalanced or prompts user adjustment.
- [ ] **Backend Validation**:
  - The API endpoint (`/api/buckets/target` and batch endpoint `/api/buckets/targets`) validates that total target weights sum to 100.0% ($\pm 0.01\%$ for float tolerance), returning HTTP 400 with a descriptive error message when unbalanced.
- [ ] **I18N Support**:
  - English and Dutch translations added for status labels ("Balanced", "Over", "Under", "Total: {total}%").
- [ ] **Automated Tests**:
  - Unit tests verifying domain/use case bucket weight validation.
  - Delivery/API tests verifying 400 rejection for unbalanced weights and 200 acceptance for 100% sum.
  - Frontend integrity & Playwright E2E tests verifying real-time badge updates and save prevention when unbalanced.
  - Test suite coverage maintained $\ge 90\%$.

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- Pure Python business rules for bucket allocation validation:
  - Add validation utility or method in `src/wealth_pilot/domain/portfolio.py` (or `bucket.py`) to verify that a set of rebalanceable buckets sums to 100% (`Decimal('100.0')`).
  - Preserves pure Python standard library conventions (using `Decimal`, no framework imports).

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- Update bucket management use cases:
  - Validate total target weight when updating targets.
  - Support atomic batch update of multiple bucket targets so users can reallocate weights across several buckets simultaneously without intermediate failure.

### 3.3 Adapters & Repositories (`src/wealth_pilot/adapters/`)
- `ConfigRepository`:
  - Ensure persistence in `portfolio.yaml` writes validated bucket target allocations atomically.

### 3.4 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- **FastAPI Endpoints (`src/wealth_pilot/delivery/web/app.py`)**:
  - `POST /api/buckets/target`: Validate new sum of active bucket targets, returning HTTP 400 if sum $\ne 100\%$.
  - `POST /api/buckets/targets`: Add batch target update endpoint accepting `{ targets: { bucket_id: weight } }` to allow atomic reallocation.
- **HTML Template (`src/wealth_pilot/delivery/web/templates/index.html`)**:
  - Add `#bucket-total-badge` and a Save button `#btn-save-bucket-targets` in the header or table action bar of the Buckets section.
- **Frontend JavaScript (`src/wealth_pilot/delivery/web/static/js/buckets.js`)**:
  - Implement `updateBucketTotalBadge()` calculating sum of all active bucket weights from table inputs.
  - Bind `oninput` to target weight inputs to provide instant feedback.
  - Enable save action only when total equals 100%.

---

## 4. Test-Driven Development (TDD) Plan

1. **Red (Tests First)**:
   - `tests/unit/domain/test_bucket_validation.py`: Unit test asserting validation fails when active weights sum $\ne 100\%$ and passes when sum $= 100\%$.
   - `tests/delivery/test_bucket_api.py`: Test `POST /api/buckets/target` and `POST /api/buckets/targets` with unbalanced sums (expect HTTP 400) and balanced 100% sums (expect HTTP 200).
   - `tests/delivery/test_frontend_integrity.py`: Test badge presence and validation functions in `buckets.js`.
   - `tests/e2e/test_ui_workflows.py`: Playwright browser test verifying badge updates dynamically on typing and save is locked when $>100\%$.
2. **Green (Implementation)**:
   - Implement domain validation logic in pure Python.
   - Implement route validation and batch endpoint in FastAPI delivery layer.
   - Implement HTML badge, input listeners, and save logic in `index.html` and `buckets.js`.
3. **Refactor & Quality**:
   - Verify Clean Architecture boundary integrity.
   - Run linter: `uv run ruff check src tests`
   - Run formatter: `uv run ruff format --check src tests`
   - Verify test suite and coverage: `uv run pytest --cov=src/wealth_pilot` ($\ge 90\%$)

---

## 5. Verification & Rollout Checklist

- [ ] Linters pass: `uv run ruff check src tests`
- [ ] Formatting passes: `uv run ruff format --check src tests`
- [ ] Documentation builds: `uv run mkdocs build --strict`
- [ ] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [ ] Frontend integrity & Playwright E2E tests pass
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR submitted with `Closes #25` and plan linked
