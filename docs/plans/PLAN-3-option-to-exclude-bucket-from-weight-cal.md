# Architecture Plan: [Issue #3] feat: option to exclude bucket from weight calculation

- **Issue**: [#3](https://github.com/tiwu/wealth-pilot/issues/3)
- **Status**: Plan Review
- **Author**: Autonomous Issue Worker
- **Date**: 2026-10-14
- **Target Branch**: `feature/issue-3-option-to-exclude-bucket-from-weight-cal`

---

## 1. Problem Statement & Motivation
### Problem & Motivation
I want to exclude the value of my house from the bucket calculations to rebalance my portfolio. Now my house takes up 80% of the pie and it's harder to balance the others relative to each other like this.

<img width="1253" height="796" alt="Image" src="https://github.com/user-attachments/assets/109c056d-7d17-421e-a6e3-e04f0ba3faa2" />

### Proposed Solution & Requirements
Buckets should have a checkbox to include/exclude them from calculations


---

### Autonomous Agent Lifecycle
Wealth Pilot uses a two-stage autonomous agent queue:
1. **Planning Stage (`agent:plan`)**: The agent will inspect this issue, formulate an architecture plan in `docs/plans/`, post it as a comment below, and transition the label to `agent:plan-review`.
2. **Implementation Stage (`agent:approved`)**: After reviewing the plan, apply the label `agent:approved` to authorize the agent to implement code, run tests, and open a linked PR (`agent:review-ready`).
3. **Manual Only**: To keep this issue human-only, remove `agent:plan` or add `agent:manual`.


---

## 2. Requirements & Acceptance Criteria
- [ ] Address core requirements stated in Issue #3
- [ ] Maintain Clean Architecture boundaries (Domain pure, Use Cases isolated, Adapters modular)
- [ ] Implement unit and integration tests with $\ge 90\%$ test coverage
- [ ] Verify zero linting errors (`uv run ruff check`) and documentation build (`uv run mkdocs build`)

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- Ensure all financial math uses `Money` / `Decimal` (no floats)
- Avoid zero-value truthiness trap (`value or fallback`)

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- Application orchestrators receive domain entities and return typed outputs

### 3.3 Adapters & Repositories (`src/wealth_pilot/adapters/`)
- Persistence via `LocalDbRepository` (SQLite) or `ConfigRepository` (YAML)

### 3.4 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- REST APIs in `src/wealth_pilot/delivery/web/app.py`
- Web UI in `src/wealth_pilot/delivery/web/templates/index.html`

---

## 4. Test-Driven Development (TDD) Plan
1. **Red**: Write test cases in `tests/` reproducing requirements and verifying failure.
2. **Green**: Write minimal implementation satisfying the tests.
3. **Refactor**: Clean up and verify full test suite passes with $\ge 90\%$ coverage.

---

## 5. Verification Checklist
- [ ] `uv run ruff check src tests`
- [ ] `uv run ruff format --check src tests`
- [ ] `uv run mkdocs build --strict`
- [ ] `uv run pytest -v --cov=src/wealth_pilot --cov-fail-under=90`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR created with `Closes #3`
