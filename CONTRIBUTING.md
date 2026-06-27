# Contributing

## Code Style

- Python 3.14+ with `from __future__ import annotations`
- Type hints required for all public functions and methods
- Follow existing patterns — check neighbouring files before writing new code
- Keep functions small and focused; one concern per function

## Linting & Formatting

```bash
ruff check .
ruff format --check .
mypy processual_api
```

Configuration is in `pyproject.toml`.

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=processual_api --cov-report=term-missing

# Run a specific file
pytest tests/api/test_health.py -v
```

- Write tests for all new functionality
- Maintain or improve coverage — target is 99%+
- Use `AsyncMock` for async dependencies
- Prefer `TestClient` for integration testing

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests first (TDD encouraged)
3. Ensure all tests pass: `pytest`
4. Run linter: `ruff check .`
5. Run type checker: `mypy processual_api`
6. Submit PR with a clear description of changes

## Project Structure

```
processual_api/          — FastAPI backend
  routers/               — HTTP endpoint handlers
  middleware/            — Request processing pipeline
  services/              — External integrations (Discord, etc.)
  adapters/              — Presentation/data adapters
  schemas/               — Pydantic request/response models
  cgt_governor/          — CGT Governor module
  billing/               — Lemon Squeezy integration
  auth/                  — JWT, API keys, authentication
  cache/                 — Redis connection and rate limiting
  db/                    — Database session management
  data/                  — JSON file storage
  static/                — Maestro Console frontend
tests/                   — Test suite
  api/                   — API endpoint tests
  integration/           — Integration tests
  security/              — Security tests
docs/                    — Documentation
```
