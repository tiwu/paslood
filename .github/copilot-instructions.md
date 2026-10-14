# GitHub Copilot Instructions for Wealth Pilot

These instructions guide GitHub Copilot when generating code, answering questions, and performing automated Pull Request reviews in this repository.

---

## 1. Project Context & Clean Architecture

Wealth Pilot is a local-first, privacy-respecting strategic wealth planning and asset allocation platform.
It uses **Clean Architecture (Hexagonal)**:
- `src/wealth_pilot/domain/`: Pure business models and Value Objects (`Asset`, `Liability`, `Bucket`, `Money`, `BalanceSheet`, `AdviceItem`). Must remain 100% pure Python with NO framework imports.
- `src/wealth_pilot/use_cases/`: Pure calculation and orchestration use cases (`CalculateBucketAllocationUseCase`, `OptimizeTaxUseCase`, `AdviseDebtPayoffUseCase`, `AdviseContributionUseCase`, `ProjectNetWorthUseCase`, `CategorizeTransactionsUseCase`, `AdviseAiUseCase`).
- `src/wealth_pilot/adapters/`: Gateways, repositories, and external integration (`ConfigRepository`, `PdtMcpGateway`, `PdtAuthManager`, `KbcCsvGateway`, `GenericCsvGateway`, `UniversalAIAdvisorClient`).
- `src/wealth_pilot/delivery/`: Web FastAPI application (`app.py`, `templates/index.html`) and Typer/Textual CLI (`cli.py`).
- `tests/`: Pytest test suite with >90% coverage.

---

## 2. Automated PR Review Guidelines for Copilot

When reviewing pull requests in this repository, rigorously verify the following rules:

### A. Architecture & Boundary Rules
- [ ] **Pure Domain**: Ensure no files in `src/wealth_pilot/domain/` import `fastapi`, `starlette`, `httpx`, `yaml`, or third-party frameworks.
- [ ] **Thin Delivery**: Ensure routes in `src/wealth_pilot/delivery/web/app.py` delegate business logic to use cases or repositories rather than embedding calculation algorithms directly in endpoints.
- [ ] **Config Persistence**: Ensure configuration updates (buckets, manual assets, manual debts, milestones) use `ConfigRepository` methods rather than opening files directly in routes.

### B. Financial Calculations & Precision
- [ ] **Monetary Precision**: All monetary values, balances, and asset prices must use the `Money` class (backed by Python's `Decimal` with 2 decimal places). Never use Python `float` for financial totals or arithmetic.
- [ ] **Zero-Value Truthiness**: Flag any code using `value or <fallback>` for numbers or financial balances. In Python, `0.0` evaluates to `False`, which erroneously triggers fallback amounts when a holding has zero balance.

### C. Testing & TDD Verification
- [ ] **Test Coverage**: Every PR adding or altering functionality in `src/` must include corresponding tests in `tests/`.
- [ ] **Headless HTTP Testing**: FastAPI web endpoints must be tested headlessly using `httpx.ASGITransport(app=test_app)` and `httpx.AsyncClient`. Do not spin up live web servers in test suites.
- [ ] **Network Mocking**: External services (PDT MCP, Google AI Studio, OpenAI) must be mocked using `respx` or `unittest.mock.AsyncMock`.

### D. Privacy & Local-First Security
- [ ] **No Hardcoded Secrets or PII**: Ensure no real user names, API keys, tokens, or personal account numbers are included in tests, code, or documentation.
- [ ] **Gitignore Compliance**: Ensure local storage files (`portfolio.yaml`, `rules.yaml`, `pdt_auth.json`, `.env`) are never committed.

### E. Frontend & User Experience
- [ ] **Safe API Parsing**: Ensure frontend `fetch()` calls in `index.html` inspect `res.ok` and handle non-200 responses gracefully without throwing unhandled `JSON.parse` syntax errors.
- [ ] **Tailwind Dark Theme**: Preserve the dark mode styling (`bg-slate-950`, cards `bg-slate-900 border border-slate-800`).
