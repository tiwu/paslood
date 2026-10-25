# AGENTS.md — Agent & Developer Guide for Wealth Pilot

This guide provides architectural principles, engineering standards, tooling commands, development recipes, and prompt templates for any automated agent or human developer contributing to **Wealth Pilot**.

---

## 1. Project Overview & Clean Architecture

**Wealth Pilot** is a local-first, privacy-respecting strategic wealth planning and asset allocation platform. It helps users manage macro asset allocation, track portfolio drift, simulate compound wealth trajectories, optimize capital gains tax (such as the Belgian 2026 tax framework), and receive strategic advice via pluggable AI advisors.

### Architectural Philosophy: Pure Clean Architecture

Wealth Pilot strictly adheres to **Clean Architecture (Hexagonal / Ports & Adapters)**. Dependencies point inward only:

```text
src/wealth_pilot/
├── domain/        # Enterprise Business Rules (Pure Python dataclasses, Value Objects)
│                  # NO framework imports (no FastAPI, Typer, YAML, or httpx)
│                  # Asset, Liability, Bucket, Money, BalanceSheet, AdviceItem
├── use_cases/     # Application Business Rules (Pure input/output orchestrators)
│                  # CalculateBucketAllocation, OptimizeTax, AdviseDebtPayoff,
│                  # AdviseContribution, ProjectNetWorth, CategorizeTransactions, AdviseAi
├── adapters/      # Interface Adapters (Gateways, Repositories, Third-Party Clients)
│   ├── ai/        # Universal AI LLM client (Gemini, OpenAI, Anthropic, Ollama)
│   ├── ingestion/ # Statement & API adapters (PDT MCP, OAuth PKCE, KBC CSV, Generic CSV)
│   └── repositories/ # ConfigRepository (portfolio.yaml, rules.yaml, pdt_auth.json)
└── delivery/      # Frameworks & Drivers (Web and CLI)
    ├── web/       # FastAPI application, REST endpoints, Jinja2 template (index.html)
    ├── cli.py     # Typer & Textual CLI application
    └── static/    # PWA manifest, service worker, icons
tests/             # Mirror directory test suite (Unit, Integration, Delivery)
```

#### Layer Boundary Rules
1. **Domain (`domain/`)**: Must remain 100% pure Python. It only imports Python standard library (`decimal`, `dataclasses`, `enum`, `typing`). Never import FastAPI, httpx, or PyYAML into domain models.
2. **Use Cases (`use_cases/`)**: Receive domain entities, execute mathematical calculations, and return domain entities or typed dictionaries. They must not depend on HTTP delivery frameworks or database specifics.
3. **Adapters (`adapters/`)**: Implement protocols/gateways for external integrations (MCP servers, OAuth endpoints, CSV parsing, YAML file persistence).
4. **Delivery (`delivery/`)**: Keep routes thin. Deliveries translate HTTP requests/CLI arguments into Use Case inputs, invoke the Use Case, and serialize output to JSON or HTML templates.

---

## 2. Tooling & CLI Commands (via `uv`)

Always use `uv` for package management, running tests, linting, formatting, and launching the application.

| Task | Command |
| :--- | :--- |
| **Install all dependencies** | `uv sync --all-extras --dev` |
| **Run all tests** | `uv run pytest` |
| **Run tests with coverage** | `uv run pytest --cov=src/wealth_pilot --cov-report=term-missing` |
| **Run specific test file** | `uv run pytest tests/delivery/test_new_features.py` |
| **Run single test function** | `uv run pytest tests/delivery/test_web.py -k test_web_index_and_overview` |
| **Lint checks** | `uv run ruff check src tests` |
| **Lint auto-fix** | `uv run ruff check --fix src tests` |
| **Format check** | `uv run ruff format --check src tests` |
| **Format code** | `uv run ruff format src tests` |
| **Run Web Dashboard** | `uv run wealth-pilot web --port 8000` (or `uv run python -m wealth_pilot.cli web`) |
| **Run CLI Status** | `uv run wealth-pilot status` |
| **Build Documentation** | `uv run mkdocs build --strict` |
| **Serve Documentation** | `uv run mkdocs serve` |
| **Add dependency** | `uv add <package>` / `uv add --dev <package>` |

---

## 3. Development Workflow: Test-Driven Development (TDD)

We strictly follow the **Red-Green-Refactor** methodology for all new features and bug fixes:

1. **🔴 Red (Test First)**:
   - Before writing or altering implementation code, write a reproduction or specification test in `tests/`.
   - Use `ASGITransport` and `AsyncClient` for FastAPI delivery tests.
   - Use `respx` or `unittest.mock.AsyncMock` for external network calls (e.g. PDT MCP or LLM APIs).
   - Confirm the test fails for the expected reason (`uv run pytest path/to/test.py`).
2. **🟢 Green (Implement)**:
   - Write the minimal, precise code required to make the test pass cleanly.
   - Respect Clean Architecture boundaries (logic in use cases, persistence in repositories, routes in delivery).
   - Confirm all tests pass (`uv run pytest`).
3. **🔵 Refactor & Lint**:
   - Clean up code structure, eliminate duplication, and preserve docstrings.
   - Run `uv run ruff check src tests` and `uv run ruff format src tests`.
   - Verify coverage meets or exceeds 90%+ (target 95%+).

---

## 4. Key Domain Rules & Guidelines

- **Zero-Value Truthiness Trap**:
  - Never use `value or <fallback>` for monetary or portfolio amounts (e.g. `sum(...) or 8100.0`). In Python, `0.0` is falsy and will erroneously trigger the fallback number. Derive values directly from actual assets or data models.
- **Precision with Currency**:
  - Always use `Money` (backed by Python's `Decimal` with 2 decimal places) for financial calculations, asset values, debts, and cashflows to prevent floating-point rounding errors.
- **Local-First & Absolute Privacy**:
  - Wealth Pilot is designed to run locally. User financial balances, account references, and tokens must never be logged to external analytics or hardcoded into repo files.
  - Configuration files (`~/.wealth_pilot/portfolio.yaml`, `pdt_auth.json`, `.env`) are strictly gitignored.
- **Belgian 2026 Capital Gains Tax Model**:
  - Pre-2026 acquisitions use the **Dec 31, 2025 closing price** as the benchmark cost basis.
  - Post-2025 acquisitions use the **actual purchase price** per share.
  - Annual capital gains exemption defaults to **€10,000.00**. Gains above the exemption are taxed at **10.0%**.
- **Portfolio Holding & Bucket Assignment**:
  - When assigning assets to buckets, matching criteria priority is: `symbols` > `isins` > `name_keywords` > `asset_classes`.
  - Re-assigning an asset cleans up matching symbols from other buckets to prevent ambiguous multi-bucket allocation.
- **Headless Web Testing**:
  - FastAPI endpoints are tested headlessly in memory using `httpx.ASGITransport(app=test_app)`. Do not spawn a live background server process during automated testing.
- **Tailwind UI Standards**:
  - Use dark mode by default (`bg-slate-950`, cards `bg-slate-900 border border-slate-800`).
  - Keep modals centered with `fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4`.

---

## 5. Developer Recipes & Prompts for Agents

When delegating tasks to subagents or prompt-chaining in this repo, use these battle-tested prompts:

### Prompt 1: Adding a New Statement Ingestion Gateway
```text
Task: Implement a new statement ingestion gateway for <Bank/Broker Name>.
Architecture Guidelines:
1. Create src/wealth_pilot/adapters/ingestion/<name>_csv.py implementing BaseIngestionGateway.
2. In domain/, ensure any new transaction categories map cleanly to Category enum.
3. Write comprehensive tests in tests/integration/test_ingestion_<name>.py with realistic mock CSV fixtures.
4. Wire the gateway into src/wealth_pilot/delivery/web/app.py under POST /api/ingest/<name>.
5. Follow Red-Green-Refactor: write tests first, verify with 'uv run pytest', and ensure zero ruff errors.
```

### Prompt 2: Adding a New Financial Advice or Simulation Use Case
```text
Task: Implement a new financial use case: <Use Case Name>.
Architecture Guidelines:
1. Place the pure calculation in src/wealth_pilot/use_cases/<use_case_file>.py.
2. Accept domain Value Objects (Money, Decimal, BalanceSheet, Asset) as inputs.
3. Write unit tests in tests/unit/use_cases/ capturing boundary conditions (zero balances, high interest, edge dates).
4. Expose the use case via a delivery route in src/wealth_pilot/delivery/web/app.py and add interactive controls in index.html.
5. Verify test coverage remains above 90% using 'uv run pytest --cov=src/wealth_pilot'.
```

### Prompt 3: Modifying Web UI Widgets & Dashboards
```text
Task: Add or update <Widget Name> in the web dashboard.
Guidelines:
1. Modify src/wealth_pilot/delivery/web/templates/index.html adhering to the slate-950 dark theme.
2. Ensure any new API responses are parsed safely (check res.ok, handle errors gracefully without crashing JSON.parse).
3. Provide keyboard accessibility and auto-updating state on modal dismissal.
4. Add delivery integration tests in tests/delivery/ asserting endpoint contracts and returned keys.
5. Verify with 'uv run ruff check src tests' and 'uv run ruff format --check src tests'.
```

---

## 6. Antigravity & AI Assistant Specifics

- **Verification Loop**: Always run `uv run pytest` and `uv run ruff check src tests` before completing any response or submitting code changes.
- **Clean Architecture Preservation**: When asked to add quick features, never take shortcuts that compromise the pure domain layer (e.g. importing `Request` or `yaml` inside `domain/`).
- **Artifacts**: When presenting architectural plans, detailed analysis, or tax simulations, write them to the designated artifacts directory in Markdown format.
- **Git Commits**: Use conventional commits (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`).

---

## 7. Autonomous Issue Queue & Feature Plan Tracking

Wealth Pilot includes an automated, asynchronous work queue driven by GitHub Issues.

### 7.1 Two-Stage Lifecycle

```text
1. User queues issue with label 'agent:plan'
2. Agent inspects issue -> writes docs/plans/PLAN-<id>-<slug>.md -> comments on issue -> sets 'agent:plan-review'
3. User reviews plan -> sets label 'agent:approved'
4. Agent creates branch feature/issue-<id>-<slug> -> implements with TDD (>=90% cov) -> opens PR -> sets 'agent:review-ready'
5. User reviews PR -> merges to main -> issue closes
```

### 7.2 Label Taxonomy

| Label | Meaning | Who Applies |
| :--- | :--- | :--- |
| `agent:plan` | Ready for agent to formulate architecture plan | Human |
| `agent:plan-review` | Plan drafted in `docs/plans/`; awaiting human review | Agent |
| `agent:approved` | Plan approved; ready for implementation | Human |
| `agent:in-progress` | Agent is actively implementing code & tests | Agent |
| `agent:review-ready` | PR opened with passing tests; awaiting human review | Agent |
| `agent:blocked` | Agent blocked on user input or credentials | Agent |
| `agent:manual` | Human-only task; agent ignores | Human |

### 7.3 Feature Plans Archive (`docs/plans/`)

Every non-trivial feature or architectural change MUST have a corresponding plan archived at:
```text
docs/plans/PLAN-<issue_number>-<slug>.md
```
Plans are indexed in `mkdocs.yml` and render directly within the built-in documentation (`/guide`) and GitHub Pages. Use `docs/plans/PLAN-TEMPLATE.md` as the baseline.

### 7.4 Running the Issue Worker & Queue Helper

The autonomous issue lifecycle is powered by the Antigravity LLM worker sidecar, assisted by `scripts/poll_issues.py` for git and GitHub label transitions:

- **Queue Inspection**:
  ```bash
  uv run python scripts/poll_issues.py --status         # Overview of all queue states
  uv run python scripts/poll_issues.py --next           # Next actionable issue (plain text)
  uv run python scripts/poll_issues.py --next --json    # Next actionable issue (JSON)
  ```

- **Lifecycle Helper Commands**:
  ```bash
  # Publish agent-authored plan from docs/plans/PLAN-<id>-<slug>.md:
  uv run python scripts/poll_issues.py --publish-plan <issue_number>

  # Start implementation on approved feature branch:
  uv run python scripts/poll_issues.py --start-work <issue_number>

  # Submit Pull Request and link issue/plan:
  uv run python scripts/poll_issues.py --submit-pr <issue_number>

  # Checkout feature branch for local testing:
  uv run python scripts/poll_issues.py --checkout <issue_number>
  ```

- **Scheduled Background Poller**: Configured via the Antigravity scheduled automation sidecar `wealth-pilot-issue-worker` running hourly (`CRON_TZ=Europe/Brussels 0 * * * *`) in `~/.gemini/config/sidecars/wealth-pilot-issue-worker/sidecar.json`, executing the `issue-worker` skill (`.agents/skills/issue-worker/SKILL.md`).


