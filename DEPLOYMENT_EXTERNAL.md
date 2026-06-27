# Deploying Processual Maestro Kernel (External Integration Guide)

## Overview

This guide covers production deployment of the **Processual Maestro Kernel v2.0.0** for external partners. The system exposes a REST API at port `8000` with JSON request/response bodies.

### Two Build Profiles

| Target | Includes CGT Engine | Use Case |
|--------|---------------------|----------|
| `public` | No (stubs) | External partners, evaluation, front-end integration |
| `full` | Yes | Internal deployments with proprietary math |

When the CGT engine (`cgtlib/private/`) is absent, all CGT endpoints return a `503` with `{"error": "private_cgt_engine_unavailable"}`. Non-CGT endpoints (auth, health, reports, workflows, billing) function normally.

---

## Quick Start (Docker)

```bash
# 1. Clone and configure
git clone <repo-url> processual-maestro
cd processual-maestro

# 2. Set environment variables
cp .env.production.example .env
# Edit .env — set strong secrets for every value

# 3. Build and start (public profile — no CGT)
docker compose build --build-arg BUILD_TARGET=public
docker compose up -d

# 4. Verify
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | **Yes** | — | HMAC key for JWT tokens (min 32 chars) |
| `CORS_ORIGINS` | **Yes** | — | Comma-separated allowed origins (no `*` in production) |
| `DATABASE_URL` | **Yes** | — | PostgreSQL async connection string |
| `REDIS_URL` | **Yes** | — | Redis connection string (with password) |
| `POSTGRES_PASSWORD` | **Yes** | — | PostgreSQL password |
| `REDIS_PASSWORD` | **Yes** | — | Redis password |
| `OPENAI_API_KEY` | No | — | OpenAI API key (LLM reports) |
| `ANTHROPIC_API_KEY` | No | — | Anthropic API key (LLM reports) |
| `GEMINI_API_KEY` | No | — | Google Gemini API key (LLM reports) |
| `DEEPSEEK_API_KEY` | No | — | DeepSeek API key (LLM reports) |
| `API_DEBUG` | No | `false` | Must be `false` in production |

> **Security**: The server rejects startup in production mode if any required secret is empty or set to a weak value (`CHANGE_ME`, `admin`, `password`, `test`, `123456`, etc.).

---

## API Authentication

All protected endpoints require a Bearer JWT token:

```http
Authorization: Bearer <token>
```

Obtain a token from `/auth/login`:

```json
{
  "username": "admin",
  "password": "<your-password>"
}
```

**Protected routers**: `/auth/*`, `/reports/*`, `/workflows/*`, `/billing/*`, `/cgt/*`.

---

## Health Checks

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health/live` | Liveness probe | `{"status": "alive"}` |
| `GET /health/ready` | Readiness probe | `{"status": "ready", "dependencies": {...}}` |

The readiness check verifies database connectivity, Redis connectivity, and CGT engine availability. The service reports `"degraded"` if any dependency is unavailable.

---

## Monitoring

- **Prometheus metrics**: `GET /metrics` (enabled by default)
- **Logs**: JSON-structured, output to stdout (Docker logging driver)
- **Health endpoints** support container orchestrator probes (Kubernetes, Nomad, Docker Swarm)

---

## Production Checklist

- [ ] All secrets set in `.env` (no defaults)
- [ ] `JWT_SECRET` is a strong, unique random string
- [ ] `CORS_ORIGINS` lists only your frontend domain(s)
- [ ] `API_DEBUG=false`
- [ ] Docker compose uses `--build-arg BUILD_TARGET=public` (or `full` with CGT)
- [ ] Health checks configured in orchestrator
- [ ] Database migrations run on first deploy
- [ ] Redis password set and matches `REDIS_URL`
- [ ] Secrets not committed to version control (`.env` in `.gitignore`)
- [ ] Release check passes: `python scripts/release_check.py`

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Startup crash: `RuntimeError: JWT_SECRET is empty` | Missing JWT_SECRET | Set in `.env` |
| `{"detail":"Not authenticated"}` | Missing/invalid token | Add `Authorization: Bearer <token>` header |
| `CGT endpoints return 503` | Public build (no private engine) | Switch to `full` build or accept limitation |
| `{"detail":"CORS origin not allowed"}` | Origin not in CORS_ORIGINS | Add origin to `CORS_ORIGINS` |
| Database connection refused | Wrong DATABASE_URL or DB not started | Check `docker compose logs db` |
| Redis connection refused | Wrong REDIS_URL or Redis not started | Check `docker compose logs redis` |

---

## Support

For deployment issues, contact the Processual Maestro Kernel team.
