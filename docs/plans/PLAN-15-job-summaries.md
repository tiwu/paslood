# Architecture Plan: [Issue #15] feat: job summaries

- **Issue**: [#15](https://github.com/tiwu/paslood/issues/15)
- **Status**: Plan Review
- **Author**: Autonomous Issue Worker
- **Date**: 2026-10-25
- **Target Branch**: `feature/issue-15-job-summaries`

---

## 1. Problem Statement & Motivation
GitHub Actions workflow runs in `tiwu/paslood` currently output build and test logs across multiple jobs (`lint`, `test` in `ci.yml`, `deploy` in `docs.yml`, and `release` in `release.yml`). To inspect whether tests passed, test coverage met the $\ge 90\%$ threshold, linters succeeded, or documentation built correctly, developers and reviewers must click through individual job execution logs and scroll through dense terminal output.

GitHub Actions provides `$GITHUB_STEP_SUMMARY`, which renders Markdown directly on the workflow run overview page (Job Summary). By adding job and step summaries to all workflows, contributors and maintainers gain immediate, high-level visibility into test results, code coverage breakdowns, lint/formatting checks, documentation builds, and release artifact distributions without navigating logs.

---

## 2. Requirements & Acceptance Criteria
- [ ] **CI Workflow (`ci.yml`) - Lint & Format Job**:
  - Appends a concise Markdown summary to `$GITHUB_STEP_SUMMARY` detailing:
    - Status of Ruff Linter (`ruff check src tests scripts`)
    - Status of Ruff Formatter (`ruff format --check src tests scripts`)
    - Status of MkDocs Documentation Build (`mkdocs build --strict`)
    - Environment metadata (Python version, uv version, OS runner)
- [ ] **CI Workflow (`ci.yml`) - Test Suite & Coverage Job**:
  - Appends a comprehensive Markdown summary to `$GITHUB_STEP_SUMMARY` detailing:
    - Overall test suite results (total passed, failed, duration)
    - Full coverage report table using `coverage report --format=markdown`
    - High-level coverage metric versus the $\ge 90\%$ target threshold
    - Runs even if preceding test steps fail (`if: always()`) so failure status is immediately visible
- [ ] **Documentation Workflow (`docs.yml`) - Deploy Job**:
  - Appends a deployment summary to `$GITHUB_STEP_SUMMARY` showing deployment target, GitHub Pages URL (`https://tiwu.github.io/paslood/`), commit SHA, and build timestamp
- [ ] **Release Workflow (`release.yml`) - Release Job**:
  - Appends a release summary to `$GITHUB_STEP_SUMMARY` listing built distribution packages (`.whl`, `.tar.gz`) from `dist/`, package sizes, and release link
- [ ] **Maintainability & Testing**:
  - Any helper scripts or CLI formatting logic created in `scripts/` are unit tested in `tests/unit/` with $\ge 90\%$ coverage
  - Workflows use clean, POSIX-compatible shell commands that execute reliably across Linux runners
- [ ] **Quality & Verification**:
  - Automated tests cover all cases with $\ge 90\%$ test coverage
  - Zero linting or formatting errors (`uv run ruff check src tests scripts` and `uv run ruff format --check src tests scripts`)
  - Documentation builds strictly (`uv run mkdocs build --strict`)

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/paslood/domain/`)
- Pure Python domain models (`Money`, `Asset`, `Liability`, `Bucket`, `BalanceSheet`, `User`, `TenantContext`) remain 100% untouched.
- Invariants maintained: zero external dependencies, pure standard library, exact `Decimal` arithmetic.

### 3.2 Use Cases Layer (`src/paslood/use_cases/`)
- Application orchestrators (`CalculateBucketAllocation`, `OptimizeTax`, `AdviseDebtPayoff`, `BuildOverview`, etc.) remain untouched.
- Pure input/output boundaries preserved.

### 3.3 Adapters & Repositories (`src/paslood/adapters/`)
- Adapters, repositories, and third-party gateways remain untouched.

### 3.4 Delivery Frameworks & CI/CD Infrastructure (`.github/workflows/`, `scripts/`)
- `.github/workflows/ci.yml`:
  - `lint`: Add step `Generate Lint & Formatting Summary` that writes Markdown table to `$GITHUB_STEP_SUMMARY`.
  - `test`: Add step `Generate Test & Coverage Summary` using `coverage report --format=markdown` and test metrics appended to `$GITHUB_STEP_SUMMARY` with `if: always()`.
- `.github/workflows/docs.yml`:
  - `deploy`: Add step `Generate Documentation Deployment Summary` writing deployment details and Pages link to `$GITHUB_STEP_SUMMARY`.
- `.github/workflows/release.yml`:
  - `release`: Add step `Generate Release Artifact Summary` listing generated distribution files in `dist/` and tag info to `$GITHUB_STEP_SUMMARY`.

---

## 4. Test-Driven Development (TDD) Plan
1. **Red (Tests First)**:
   - If auxiliary summary generators or formatting helpers are created in `scripts/` (e.g. `scripts/ci_summary.py`), write unit tests in `tests/unit/test_ci_summary.py` asserting markdown structure, coverage threshold evaluation, and edge case resilience (missing files, exit code propagation).
   - Verify tests fail prior to script implementation.
2. **Green (Implementation)**:
   - Implement helper scripts and update `.github/workflows/ci.yml`, `.github/workflows/docs.yml`, and `.github/workflows/release.yml` with step summary generation.
   - Verify workflow syntax and run local validation.
3. **Refactor & Quality**:
   - Ensure clean formatting and no lint warnings (`uv run ruff check src tests scripts`).
   - Validate documentation build (`uv run mkdocs build --strict`).
   - Verify overall test coverage remains $\ge 90\%$ (`uv run pytest --cov=src/paslood --cov-fail-under=90`).

---

## 5. Verification & Rollout Checklist
- [ ] Linters pass: `uv run ruff check src tests scripts`
- [ ] Formatting passes: `uv run ruff format --check src tests scripts`
- [ ] Documentation builds: `uv run mkdocs build --strict`
- [ ] Test suite passes with $\ge 90\%$ coverage: `uv run pytest`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Architecture plan committed and pushed to `feature/issue-15-job-summaries`
- [ ] Issue #15 updated with plan preview and transitioned to `agent:plan-review` via `scripts/poll_issues.py --publish-plan 15`
