# Release Notes — Processual Maestro Kernel v2.0.0

## Overview

Clean local governance reference build with unified API responses, automated release packaging, and pre-release validation.

## What's New

### Security Hardening
- **Secrets validation**: Production startup rejects all weak/default secrets (not just JWT_SECRET)
- **CORS wildcard rejection**: `CORS_ORIGINS=*` raises `RuntimeError` in production — explicit origins required
- **Adapter KeyError fix**: All LLM adapters use `os.environ.get()` with descriptive `RuntimeError` instead of crashing on missing keys
- **Error handler middleware**: Stack traces suppressed in production (500 responses return `{"detail": "..."}`)
- **Docs disabled in production**: `/docs` and `/redoc` unavailable in production mode

### Public Build Profile
- **`Dockerfile` public target**: Ships without proprietary CGT engine (`cgtlib/private/` excluded)
- **`cgtlib/_fallback.py`**: Graceful stubs for all ~100 public CGT API functions — return structured `503` instead of crashing
- **README updated**: Routes table matches actual API (no `/api/v2/` prefix)

### Authentication Coverage
- **Reports router** (`/reports/*`): All endpoints require `Depends(get_current_user)`
- **Workflows router** (`/workflows/*`): All endpoints require `Depends(get_current_user)`

### Operational
- **Health endpoint** (`/health/ready`): Reports actual CGT engine availability (`_HAS_PRIVATE`)
- **Docker Compose hardened**: Healthchecks, resource limits, read-only filesystem, internal network, version-pinned images, all secrets required via `:?`
- **`scripts/release_check.py`**: Automated pre-release validation (cache artifacts, weak secrets, pytest threshold, Docker build, data artifacts)
- **`.env.production.example`**: Reference template with all required variables documented

### Documentation
- **`DEPLOYMENT_EXTERNAL.md`**: Comprehensive external integration guide
- **`RELEASE_NOTES.md`**: This file
- **`EXTERNAL_READINESS_REPORT.md`**: External-facing readiness report

## Breaking Changes

1. **`CORS_ORIGINS` must be explicit in production** — wildcard `*` no longer allowed
2. **All reports and workflows endpoints now require authentication** — update clients to pass JWT Bearer tokens
3. **Secrets validation is strict** — startup fails if any required secret is empty or set to a weak value
4. **Public build has no CGT engine** — CGT endpoints return `503` with `{"error": "private_cgt_engine_unavailable"}`

## API Changes

| Change | Detail |
|--------|--------|
| Auth required on `/reports/*` | All POST endpoints added `Depends(get_current_user)` |
| Auth required on `/workflows/*` | All endpoints added `Depends(get_current_user)` |
| `/health/ready` | `cgtlib` field now reflects actual engine availability |
| `/docs` | Disabled in production |
| `/openapi.json` | Available (returns schema without credentials) |

## Test Results

- **957 total tests**, 952 passed, 5 skipped (platform-conditional), **0 failures, 0 errors**
- **0 known failures** — atexit bridge teardown race condition on Windows is resolved
- Report: `docs/reports/pytest_result_final.txt`

## Build Profiles

```bash
# Public (no CGT engine)
docker build --target public -t processual-maestro:public .

# Full (includes CGT engine — internal only)
docker build --target full -t processual-maestro:full .
```

## Upgrade Notes

1. Update `.env` with all required variables (see `.env.production.example`)
2. Set `JWT_SECRET` to a strong random string (min 32 characters)
3. Set `CORS_ORIGINS` to explicit origins (comma-separated)
4. Ensure `API_DEBUG=false` in production
5. Rebuild Docker images with `docker compose build --no-cache`
6. Run `python scripts/release_check.py` to validate deployment readiness
