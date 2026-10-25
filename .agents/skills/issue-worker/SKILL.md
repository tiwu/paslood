---
name: issue-worker
description: Autonomous queue worker protocol for Wealth Pilot. Polls issues, drafts architecture plans, executes TDD implementations, and submits pull requests without exploratory drift.
---

# Wealth Pilot Autonomous Issue Worker Protocol

## Purpose
Deterministic, minimal-overhead execution protocol for processing Wealth Pilot GitHub issues (`agent:plan` and `agent:approved`).

---

## Strict Guardrails (What NEVER to Do)

1. **NEVER read or inspect `scripts/poll_issues.py`**. The script is a black-box CLI tool. Rely only on its flags and return values.
2. **NEVER create scratch or probe files** (e.g., `touch docs/plans/test-temp.md`).
3. **NEVER inspect git commit logs, workflows (`.github/workflows`), or `pyproject.toml`** unless the issue explicitly requests changes to them.
4. **NEVER loop or re-check the queue** after finishing a plan or PR. Process exactly ONE issue per run, then exit.
5. **DO NOT read prior plan examples** (`PLAN-3-...`, etc.). Only read `docs/plans/PLAN-TEMPLATE.md`.
6. **Limit exploration**: Inspect at most 3 source files directly relevant to the issue domain before drafting.

---

## Step-by-Step Execution Protocol

### Step 0: Check Queue

Execute:
```bash
uv run python scripts/poll_issues.py --next --json
```

- If `stage` is `null` or JSON is empty:
  - Print `"Queue clear."` and exit immediately. Make no more tool calls.

---

### Step 1: Planning Stage (`stage == "planning"`)

When `stage` is `"planning"`:

1. **Parse Issue Data**:
   - Extract `number`, `title`, `body`, and compute `slug`.
2. **Targeted Code Reading**:
   - Read only the specific file(s) in `src/wealth_pilot/` directly affected by the feature (max 3 files).
3. **Read Plan Template**:
   - Read `docs/plans/PLAN-TEMPLATE.md`.
4. **Author Architecture Plan**:
   - Write plan to `docs/plans/PLAN-<number>-<slug>.md`.
   - Adhere to Clean Architecture:
     - Domain: Pure Python, Decimal, invariants.
     - Use Cases: Pure business logic, port interfaces.
     - Adapters: Gateways, repositories, ingestion.
     - Delivery: Web/CLI routes.
5. **Verify MkDocs Build**:
   ```bash
   uv run mkdocs build --strict
   ```
6. **Publish Plan**:
   ```bash
   uv run python scripts/poll_issues.py --publish-plan <number>
   ```
7. **Complete**:
   - Print `"Plan published for issue #<number>."` and finish. Do NOT run further commands.

---

### Step 2: Implementation Stage (`stage == "implementation"`)

When `stage` is `"implementation"`:

1. **Start Work & Branch**:
   ```bash
   uv run python scripts/poll_issues.py --start-work <number>
   ```
2. **Read Approved Plan**:
   - Read `docs/plans/PLAN-<number>-<slug>.md`.
3. **Red (Test First)**:
   - Write unit and delivery tests in `tests/`.
   - Run tests to verify failure:
     ```bash
     uv run pytest tests/path/to/new_test.py
     ```
4. **Green (Minimal Implementation)**:
   - Implement minimal required code in `src/wealth_pilot/`.
5. **Verification**:
   ```bash
   uv run pytest --cov=src/wealth_pilot
   uv run pytest tests/delivery/test_frontend_integrity.py tests/e2e/test_ui_workflows.py
   uv run ruff check src tests
   uv run ruff format --check src tests
   uv run mkdocs build --strict
   ```
6. **Update Changelog & Commit**:
   - Add entry under `## [Unreleased]` in `CHANGELOG.md`.
   - Stage and commit:
     ```bash
     git add src tests CHANGELOG.md docs
     git commit -m "feat/fix(#<number>): <terse description>"
     ```
7. **Submit Pull Request**:
   ```bash
   uv run python scripts/poll_issues.py --submit-pr <number>
   ```
8. **Complete**:
   - Print `"PR submitted for issue #<number>."` and finish. Do NOT run further commands.
