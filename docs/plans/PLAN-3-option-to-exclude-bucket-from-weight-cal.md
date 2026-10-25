# Architecture Plan: [Issue #3] feat: option to exclude bucket from weight calculation

- **Issue**: [#3](https://github.com/tiwu/wealth-pilot/issues/3)
- **Status**: Completed
- **Author**: Autonomous Issue Worker
- **Date**: 2026-10-14
- **Target Branch**: `feature/issue-3-option-to-exclude-bucket-from-weight-cal`

---

## 1. Problem Statement & Motivation
Allow users to exclude illiquid or anchor assets (such as a primary residence) from dynamic portfolio rebalancing calculations. For example, if a primary residence represents 80% of total assets, including it in liquid allocation buckets skews target rebalancing calculations across liquid investments.

### Proposed Solution
Add an `excluded` boolean flag to `Bucket` models and provide a toggle in the UI so excluded buckets are omitted from target allocation weights and deposit rebalancing math while still being counted toward total net worth.

---

## 2. Requirements & Acceptance Criteria
- [x] Add `excluded: bool = False` to `Bucket` domain model
- [x] Update `CalculateBucketAllocationUseCase` to omit excluded buckets when computing target weights and buy recommendations
- [x] Maintain total net worth tracking across all assets regardless of bucket exclusion status
- [x] Add UI checkbox toggle in the Add/Edit Bucket modal
- [x] Unit and integration tests cover exclusion scenarios with $\ge 90\%$ test coverage
- [x] Zero linting errors (`uv run ruff check`) and documentation build (`uv run mkdocs build`)

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- `Bucket`: added `excluded: bool = False` attribute
- Maintained pure Python and `Decimal` financial arithmetic

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- `CalculateBucketAllocationUseCase`: filters out excluded buckets during allocation proportion and rebalance calculation

### 3.3 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- Web UI in `src/wealth_pilot/delivery/web/templates/index.html` updated with excluded badge and modal toggle

---

## 4. Test-Driven Development (TDD) Plan
1. **Red**: Unit test verifying that an excluded bucket receives 0.00% target allocation and 0 euro contribution recommendation.
2. **Green**: Filter out `bucket.excluded` in allocation calculation.
3. **Refactor**: Clean up and verify all tests pass with $\ge 90\%$ coverage.

---

## 5. Verification Checklist
- [x] `uv run ruff check src tests`
- [x] `uv run ruff format --check src tests`
- [x] `uv run mkdocs build --strict`
- [x] `uv run pytest -v --cov=src/wealth_pilot --cov-fail-under=90`
- [x] PR merged with `Closes #3`
