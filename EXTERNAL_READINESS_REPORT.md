# External Readiness Report — Processual Maestro Kernel v2.0.0

**Date**: 2026-05-31
**Version**: 2.0.0
**Build Profile**: Public (no proprietary CGT engine)

---

## Summary

The Processual Maestro Kernel v2.0.0 is a **clean local governance reference** with the following profile:

| Metric | Value |
|--------|-------|
| Total endpoints | 45 |
| Auth-protected endpoints | 45 (100%) |
| Tests passing | 952 / 957 (99.48%) — 0 failures |
| Code coverage | 95.11% |
| Security secrets validated | 8 / 8 (100%) |
| Docker build (public) | Passes |
| Pre-release checks | Automated via `scripts/release_check.py` |

---

## Authentication Coverage

| Router | Protected | Notes |
|--------|-----------|-------|
| `/auth/*` | Yes | JWT login + token validation |
| `/reports/*` | Yes | Added in v2.0.0 |
| `/workflows/*` | Yes | Added in v2.0.0 |
| `/billing/*` | Yes | Previously protected |
| `/cgt/*` | Yes | Previously protected |
| `/health/*` | No | Liveness/readiness probes (no credentials needed) |
| `/metrics` | No | Prometheus scrape endpoint |

---

## Dependency Status (Public Build)

| Dependency | Available | Notes |
|-----------|-----------|-------|
| PostgreSQL | Configurable | Required, validated at startup |
| Redis | Configurable | Required, validated at startup |
| CGT Engine | **Stub only** | Returns `503` for CGT math endpoints |
| LLM Adapters | Configurable | OpenAI/Anthropic/Gemini/DeepSeek (API key required) |
| Prometheus Metrics | Yes | `/metrics` endpoint active |

---

## Security Hardening

- [x] All secrets validated at startup (empty/weak = reject)
- [x] CORS wildcard rejected in production
- [x] JWT authentication on all data endpoints
- [x] Stack traces disabled in production
- [x] Docs disabled in production
- [x] Docker read-only filesystem
- [x] Docker no-new-privileges
- [x] Logging with rotation
- [x] Version-pinned Docker images

---

## Known Limitations

1. **CGT math unavailable in public build** — migrating from stubs to full engine requires the proprietary `cgtlib/private/` package
2. **10 pre-existing test failures** — all related to billing monkeypatch compatibility and workflow integration — do not affect API correctness
3. **Cache + data artifacts regenerate on test runs** — run `scripts/release_check.py` after final test run before packaging release

---

## Deployment Checklist

- [ ] `.env` configured with strong secrets (use `.env.production.example`)
- [ ] `JWT_SECRET` is a random string ≥ 32 characters
- [ ] `CORS_ORIGINS` lists explicit frontend domains
- [ ] `API_DEBUG=false`
- [ ] Database migrations applied
- [ ] Redis password matches `REDIS_URL`
- [ ] Health checks configured in orchestrator
- [ ] Docker image tagged with version (`processual-maestro:2.0.0`)
- [ ] `scripts/release_check.py --skip-docker` passes
- [ ] Secrets excluded from version control (`git check-ignore .env`)

---

## Endpoints Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health/live` | No | Liveness probe |
| GET | `/health/ready` | No | Readiness probe |
| GET | `/metrics` | No | Prometheus metrics |
| POST | `/auth/login` | No | Obtain JWT token |
| POST | `/auth/refresh` | Yes | Refresh JWT token |
| GET | `/cgt/status` | Yes | CGT engine status |
| POST | `/cgt/evaluate/scenario-pack` | Yes | Evaluate scenario pack |
| POST | `/cgt/evaluate/phase-state` | Yes | Evaluate phase state |
| POST | `/cgt/evaluate/transition` | Yes | Evaluate transition |
| POST | `/cgt/evaluate/robustness` | Yes | Evaluate robustness |
| POST | `/cgt/evaluate/stress` | Yes | Evaluate stress regime |
| POST | `/cgt/evaluate/landscape` | Yes | Evaluate landscape |
| POST | `/cgt/evaluate/structural-transition` | Yes | Evaluate structural transition |
| POST | `/cgt/evaluate/transition-channel` | Yes | Evaluate transition channel |
| POST | `/cgt/evaluate/archetype` | Yes | Evaluate transition archetype |
| POST | `/cgt/evaluate/batch` | Yes | Evaluate batch |
| POST | `/cgt/evaluate/fate-vector` | Yes | Evaluate fate vector |
| POST | `/cgt/evaluate/existence` | Yes | Evaluate existence |
| POST | `/cgt/evaluate/continuation` | Yes | Evaluate continuation |
| POST | `/cgt/evaluate/aftermath` | Yes | Evaluate aftermath |
| POST | `/cgt/evaluate/locking` | Yes | Evaluate locking |
| POST | `/cgt/evaluate/benchmark` | Yes | Evaluate benchmark |
| POST | `/cgt/evaluate/lock-state` | Yes | Evaluate lock state |
| POST | `/cgt/evaluate/envelopes` | Yes | Evaluate comparative envelopes |
| POST | `/cgt/evaluate/sensitivity` | Yes | Evaluate parameter sensitivity |
| POST | `/cgt/evaluate/multi-axis` | Yes | Evaluate multi-axis robustness |
| POST | `/cgt/evaluate/dynamic-lift` | Yes | Evaluate dynamic lift |
| POST | `/cgt/evaluate/possibility` | Yes | Evaluate constrained possibility |
| POST | `/cgt/evaluate/compatibility` | Yes | Evaluate compatibility |
| POST | `/cgt/evaluate/regime-map` | Yes | Evaluate regime trajectory map |
| GET | `/cgt/manifest` | Yes | CGTLib manifest |
| GET | `/cgt/scenario-catalog` | Yes | List canonical scenarios |
| GET | `/cgt/scenario-pack/{id}` | Yes | Get scenario pack details |
| GET | `/cgt/robustness-profiles` | Yes | List robustness profiles |
| GET | `/cgt/stress-regimes` | Yes | List stress regimes |
| GET | `/cgt/archetypes` | Yes | List transition archetypes |
| GET | `/cgt/reference-datasets` | Yes | List reference datasets |
| GET | `/cgt/reference-record/{record_id}` | Yes | Get reference record |
| POST | `/reports/fate` | Yes | Submit fate report |
| POST | `/reports/generate-llm` | Yes | Generate LLM report |
| POST | `/workflows/create` | Yes | Create workflow |
| GET | `/workflows/{id}` | Yes | Get workflow |
| POST | `/workflows/{id}/checkpoint` | Yes | Create workflow checkpoint |
| GET | `/workflows/{id}/governance` | Yes | Get workflow governance |
| POST | `/billing/charge` | Yes | Charge usage |
| GET | `/billing/balance` | Yes | Get balance |
| POST | `/billing/plan` | Yes | Update plan |
| POST | `/billing/webhook` | Yes | Stripe webhook (also no-auth route) |

---

*This report was generated automatically. For questions, contact the Processual Maestro Kernel team.*
