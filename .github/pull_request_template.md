## Description of Changes

Please provide a concise summary of the changes proposed in this Pull Request.

---

## Type of Change

- [ ] `feat`: New feature (non-breaking change which adds functionality)
- [ ] `fix`: Bug fix (non-breaking change which resolves an issue)
- [ ] `test`: Adding or updating automated tests
- [ ] `refactor`: Code restructuring without behavioral changes
- [ ] `docs`: Documentation updates (MkDocs or README)

---

## Architectural & Quality Checklist

Please ensure all checks are satisfied before requesting review:

### Architecture & Domain Integrity
- [ ] Domain models in `src/paslood/domain/` remain pure Python with NO framework dependencies.
- [ ] Business logic resides in Use Cases, not in web routes or controllers.
- [ ] All financial values use `Money` and `Decimal` (no floating-point money math).
- [ ] Avoided the zero-value truthiness trap (`value or fallback`).
- [ ] Documentation is updated and clear.

### Testing & Verification
- [ ] Automated tests added or updated in `tests/` capturing all changes.
- [ ] All tests pass locally: `uv run pytest`.
- [ ] Test coverage meets or exceeds 90%: `uv run pytest --cov=src/paslood`.
- [ ] Ruff linting passes: `uv run ruff check src tests`.
- [ ] Ruff formatting passes: `uv run ruff format --check src tests`.

### Privacy & Security
- [ ] No personal financial records, tokens, credentials, or private account numbers are committed.
- [ ] Sensitive configuration files are gitignored.

---

## Related Issues / Discussions
Closes #
