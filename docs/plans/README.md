# Architecture & Feature Plans

This directory serves as the persistent, version-controlled repository for all architectural proposals, feature designs, and bug fix plans in **Wealth Pilot**.

---

## 1. Plan Lifecycle & Two-Stage Queue

Feature plans bridge human requirements and autonomous agent implementation.

```text
[User Opens Issue]
      │ (with 'agent:plan')
      ▼
[Stage 1: Planning]
  - Autonomous Agent analyzes requirements & codebase
  - Agent writes: docs/plans/PLAN-<id>-<slug>.md
  - Agent posts plan comment on issue
  - Label transitions to: 'agent:plan-review'
      │
      ▼
[Human Review Checkpoint]
  - User reviews plan, requests adjustments or confirms
  - User transitions label to: 'agent:approved'
      │
      ▼
[Stage 2: Implementation]
  - Agent pulls latest main and creates branch: feature/issue-<id>-<slug>
  - Agent implements with TDD (tests first, then code)
  - Agent verifies: Ruff (0 errors) + MkDocs + Pytest (>= 90% coverage)
  - Agent commits, pushes branch, and opens PR with 'Closes #<id>'
  - Label transitions to: 'agent:review-ready'
      │
      ▼
[Stage 3: Review & Merge]
  - User reviews PR and tests
  - User merges to main; issue automatically closes
```

---

## 2. Naming Convention

Every plan file MUST follow this naming structure:

```text
docs/plans/PLAN-<issue_number>-<kebab_title>.md
```

Examples:
- `docs/plans/PLAN-002-balance-sheet-csv-export.md`
- `docs/plans/PLAN-003-belgian-tax-fifo-lookup.md`

---

## 3. Standard Plan Template

When drafting a new plan, use [`PLAN-TEMPLATE.md`](PLAN-TEMPLATE.md) as the baseline. Each plan must cover:
1. **Overview & Acceptance Criteria**
2. **Hexagonal Architecture Layer Impact** (`domain`, `use_cases`, `adapters`, `delivery`)
3. **Test-Driven Development (TDD) Strategy** (Red-Green-Refactor)
4. **Quality & Verification Checks** (90%+ coverage, linting, formatting)
