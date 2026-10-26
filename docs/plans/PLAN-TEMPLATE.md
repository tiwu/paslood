# Architecture Plan: [Issue #N] [Feature Title]

- **Issue**: [#N](https://github.com/tiwu/paslood/issues/N)
- **Status**: Proposed | Plan Review | Approved | In Progress | Completed
- **Author**: Autonomous Agent / Contributor
- **Date**: YYYY-MM-DD
- **Target Branch**: `feature/issue-N-<slug>`

---

## 1. Problem Statement & Motivation
<!-- What problem does this solve? What user need does it address? -->

---

## 2. Requirements & Acceptance Criteria
<!-- Explicit functional and non-functional requirements -->
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Automated tests cover all cases with $\ge 90\%$ test coverage

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- Entities / Value Objects modified or introduced
- Invariants maintained (pure Python, Decimal money arithmetic, no framework imports)

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- Application orchestrators added or updated
- Pure input/output interfaces

### 3.3 Adapters & Repositories (`src/wealth_pilot/adapters/`)
- Gateways, database schemas (`LocalDbRepository`), external API clients

### 3.4 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- REST endpoints in `app.py`, template additions in `index.html`, CLI commands in `cli.py`

---

## 4. Test-Driven Development (TDD) Plan
1. **Red (Tests First)**:
   - Specific unit tests in `tests/unit/`
   - Specific delivery/integration tests in `tests/delivery/`
2. **Green (Implementation)**:
   - Minimal implementation code in `src/wealth_pilot/`
3. **Refactor & Quality**:
   - Clean architecture check
   - Zero lint errors (`uv run ruff check`)
   - Format check (`uv run ruff format --check`)
   - 90%+ coverage (`uv run pytest --cov=src/wealth_pilot --cov-fail-under=90`)

---

## 5. Verification & Rollout Checklist
- [ ] Linters pass: `uv run ruff check src tests`
- [ ] Formatting passes: `uv run ruff format --check src tests`
- [ ] Documentation builds: `uv run mkdocs build --strict`
- [ ] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR submitted with `Closes #N` and plan linked
