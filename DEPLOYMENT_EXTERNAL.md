# Deploying Processual Maestro Kernel (External Integration Guide)

## Overview

This guide covers deployment of **Processual Maestro Kernel v2.0.0** for external partners. The REST API listens on port `8000`.

Passing repository or image checks is necessary evidence only. Final production readiness remains operator-controlled and requires exact-SHA CI/runtime qualification.

## Build profiles

| Target | Private CGT engine | Intended use |
|---|---|---|
| `public` | No | External partners, evaluation, front-end integration |
| `private` | Yes | Internal/private deployments with proprietary CGT compute |

The `public` image includes the complete public `cgtlib` surface and explicitly excludes `cgtlib/private`. Private-only CGT operations fail closed. Non-private API surfaces remain available according to their own authority and dependency requirements.

Readiness is profile-aware:

- `public`: private CGT is **not** a required readiness dependency;
- `private`: private CGT **is** required;
- failure of any required dependency returns HTTP `503` with `status=degraded`;
- liveness remains separate at `/health/live`.

---

## Quick start with Docker Compose

```bash
git clone <repo-url> processual-maestro
cd processual-maestro
cp .env.production.example .env
# Replace every placeholder and load real secrets from an appropriate secret store.
docker compose build api
docker compose up -d
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

`docker-compose.yml` uses the public target for the external profile. Redis is password-protected and its container healthcheck authenticates using `REDISCLI_AUTH`. Grafana is bound to `127.0.0.1:3000` by default and must not be treated as a public application endpoint.

---

## Required production authority/configuration

The deployment must remain aligned with `.env.production.example` and `processual_api/release_gate.py`.

Core values include:

- `ENVIRONMENT=production`
- `APP_ENV=production`
- `API_DEBUG=false`
- `JWT_SECRET`
- `API_KEYS`
- `PROCESSUAL_CRYPTO_KEY_B64`
- `CORS_ORIGINS`
- `DATABASE_URL`
- `POSTGRES_PASSWORD`
- `REDIS_URL`
- `REDIS_PASSWORD`
- `GRAFANA_ADMIN_PASSWORD`
- `MAESTRO_ADMIN_EMAIL`
- `MAESTRO_ADMIN_PASSWORD`
- `AUTH_TOKEN_PEPPER`
- `AUTH_RATE_LIMIT_PEPPER`
- `AUTH_DELIVERY_KEY_RING_JSON`
- `AUTH_DELIVERY_CURRENT_KEY_VERSION`
- `AUTH_PUBLIC_BASE_URL`
- `AUTH_MFA_KEY_RING_JSON`
- `AUTH_MFA_CURRENT_KEY_VERSION`
- `ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON`
- `ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION`

Provider-specific credentials are required only for the provider selected by policy. Real secret values must remain in `.env` outside version control or be injected from a deployment secret manager such as **Docker secrets**, **Kubernetes secrets**, **Google Secret Manager**, or an equivalent managed secret store.

Provider credentials are not bundled with Processual Maestro. They remain customer/deployer-owned and must never be committed to the repository or emitted into logs, reports, browser storage, or qualification evidence.

---

## Authentication and identity runtime

Protected endpoints require the appropriate authenticated authority. Identity registration/session/recovery runtimes are fail-closed when required database, Redis, token pepper, rate-limit pepper, delivery key-ring, MFA key-ring, or related authority configuration is unavailable.

Do not interpret `/health/live` as proof that registration, session, recovery, billing, or Evaluation authority is usable. Use `/health/ready`, targeted qualification, and the relevant E2E evidence.

---

## Health checks

| Endpoint | Meaning | Healthy result |
|---|---|---|
| `GET /health/live` | Process is alive | HTTP 200, `status=alive` |
| `GET /health/ready` | Required runtime dependencies for the selected profile are available | HTTP 200, `status=ready` |

A required dependency failure returns HTTP `503` and `status=degraded`.

The payload includes dependency state and indicates whether `private_cgt_required` is true for the deployed profile.

---

## Monitoring boundary

- Prometheus metrics: `GET /metrics` on the API service.
- Redis and PostgreSQL are internal Compose services.
- Prometheus uses the internal network.
- Grafana is host-loopback only by default: `127.0.0.1:3000`.
- Do not publish Grafana, Redis, PostgreSQL, or internal monitoring endpoints to the public internet without a separately reviewed access-control design.

---

## Static pre-release checks

Run:

```bash
python scripts/release_check.py
```

This verifies repository/package hygiene, current production-template coverage, pytest, the public Docker build when Docker is available, and that the public Docker artifact excludes private CGT runtime authority.

A passing result is intentionally worded as:

`STATIC PRE-RELEASE CHECKS PASS — operator/runtime qualification is still required`

It is **not** a production-readiness verdict.

---

## Windows launch-hardening qualification

For Windows PowerShell 5.1 or newer, use:

```powershell
.\scripts\qualify_launch_hardening_winps51.ps1 -ExpectedSha <exact-sha>
```

Optional executable evidence can then be enabled explicitly:

```powershell
.\scripts\qualify_launch_hardening_winps51.ps1 `
  -ExpectedSha <exact-sha> `
  -IncludeDocker `
  -IncludeGitHub
```

After loading the intended staging/production environment without printing secrets:

```powershell
.\scripts\qualify_launch_hardening_winps51.ps1 `
  -ExpectedSha <exact-sha> `
  -IncludeProductionReleaseGate `
  -IncludeDocker `
  -IncludeCompose `
  -IncludeGitHub `
  -IncludeRemote `
  -RemoteBaseUrl https://<candidate-host>
```

Evidence is written to `launch-hardening-results/` as text and JSON. Do not paste raw secrets into command arguments or reports.

---

## Production checklist

- [ ] Freeze one exact candidate SHA.
- [ ] Working tree and `git diff --check` clean.
- [ ] Full public CI/security suite executes and is green on that exact SHA.
- [ ] Public Docker image builds and contains no `cgtlib/private` tree.
- [ ] `/health/live` is healthy on the deployed exact SHA.
- [ ] `/health/ready` is HTTP 200 on the deployed exact SHA; any required dependency failure must be HTTP 503.
- [ ] Redis password matches `REDIS_URL`; Redis healthcheck authenticates.
- [ ] CORS origins are explicit HTTPS origins.
- [ ] Identity authority secrets/key rings are configured through a secret manager.
- [ ] Grafana remains loopback/internal unless a separately reviewed access boundary is deployed.
- [ ] Database migrations and exact Alembic head are qualified using the release contract.
- [ ] Backup/restore and rollback procedures are documented and exercised as required by the launch gate.
- [ ] Secrets are absent from repository, logs, reports, browser storage, and generated evidence.
- [ ] External Evaluation E2E and required provider/billing tests are green or explicitly out of launch scope.
- [ ] Private overlay qualification is green if private components participate in production.
- [ ] Human operator reviews the final evidence and explicitly authorizes merge/release.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| API startup fails for missing authority values | Required production env/secret is missing | Compare against `.env.production.example` and the release gate; do not add insecure fallbacks |
| `/health/live` = 200 but `/health/ready` = 503 | Required dependency is unavailable | Inspect dependency projection; repair DB/Redis/adapter/private-CGT requirement as applicable |
| Public CGT operation returns unavailable | Public build intentionally excludes private compute | Use a qualified private deployment only when private CGT is part of the approved architecture |
| Redis remains unhealthy | Password/`REDIS_URL` mismatch or Redis cannot authenticate | Verify secret-managed password and authenticated healthcheck |
| Browser CORS failure | Origin is not explicitly allowed | Add the exact HTTPS origin; do not use wildcard in production |
| Grafana reachable outside localhost | Host/network publishing was changed | Restore loopback/internal binding or perform a dedicated monitoring access-control review |

---

## Authority invariant

`Policy / Authority -> Admission -> Execution -> Evidence`

Health checks, agents, sandbox runtimes, dashboards, and qualification scripts are evidence/operations surfaces. They do not grant authority and do not issue the final production-readiness verdict.
