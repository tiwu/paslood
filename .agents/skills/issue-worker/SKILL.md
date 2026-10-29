---
name: issue-worker
description: Autonomous queue worker protocol for Paslood. Polls issues, drafts architecture plans, executes TDD implementations, and submits pull requests without exploratory drift.
---

# Paslood Autonomous Issue Worker Protocol

## Purpose
Deterministic, minimal-overhead execution protocol for processing Paslood GitHub issues (`agent:plan` and `agent:approved`).

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
   - Read only the specific file(s) in `src/paslood/` directly affected by the feature (max 3 files).
3. **Read Plan Template**:
   - Read `docs/plans/PLAN-TEMPLATE.md`.
4. **Author Architecture Plan**:
   - Write plan to `docs/plans/PLAN-<number>-<slug>.md`.
   - Adhere to Clean Architecture:
     - Domain: Pure Python, Decimal, invariants.
     - Use Cases: Pure business logic, port interfaces.
     - Adapters: Gateways, repositories, ingestion.
     - Delivery: Web/CLI routes.
   - Include update of documentation, unit tests, and delivery tests in the plan.
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
   - Implement minimal required code in `src/paslood/`.
   - If `input.css`, `tailwind.config.js`, or template utility classes changed, recompile CSS:
     ```bash
     npm run build:css
     ```
5. **Visual Rendering & Screenshot Review (Mandatory for Web UI / Frontend Changes)**:
   - Whenever `src/paslood/delivery/web/` (templates, CSS, or static JS) is modified:
     1. **Render Screenshots**: Launch an ephemeral seeded FastAPI server with Playwright Chromium (`1440×960` @ `2x` Retina scale) and capture full-page screenshots of the affected workspace(s) in **both** Dark ("Midnight Blueprint") and Light ("Architectural Vellum") modes into `docs/assets/screenshots/`.
     2. **Inspect Rendered Output**: Use the `read` tool on each generated PNG to visually audit the actual browser rendering before delivery:
        - Verify light-theme and dark-theme surface bindings, text contrast ($\ge 4.5:1$), and Chart.js / SVG colors render cleanly with zero unstyled dark boxes in light mode or unreadable white-on-white labels.
        - Verify no text, formulas, or table cells overflow card boundaries, and confirm Refactoring UI hierarchy (`p-6` padding, `gap-6` spacing, 1 primary button per toolbar).
     3. **Iterate Before Delivery**: If any visual defect is visible in the screenshot, fix the CSS/DOM/JS, run `npm run build:css`, re-render, and re-inspect the PNG until clean.
6. **Automated Verification**:
   ```bash
   uv run pytest --cov=src/paslood
   uv run pytest tests/delivery/test_frontend_integrity.py tests/e2e/test_ui_workflows.py
   uv run ruff check src tests
   uv run ruff format --check src tests
   uv run mkdocs build --strict
   ```
7. **Update Changelog & Commit**:
   - Add entry under `## [Unreleased]` in `CHANGELOG.md`.
   - Stage and commit (including `docs/assets/screenshots/` when UI changes were made):
     ```bash
     git add src tests CHANGELOG.md docs
     git commit -m "feat/fix(#<number>): <terse description>"
     ```
8. **Submit Pull Request & Attach Screenshots**:
   ```bash
   uv run python scripts/poll_issues.py --submit-pr <number>
   ```
   - For UI changes, embed the committed `docs/assets/screenshots/*.png` images (`https://raw.githubusercontent.com/tiwu/paslood/<branch>/docs/assets/screenshots/...`) in the PR description (`gh pr edit`) so reviewers can inspect both themes directly on GitHub.
9. **Complete**:
   - Print `"PR submitted for issue #<number>."` and finish. Do NOT run further commands.
