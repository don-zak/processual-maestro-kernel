# Processual Maestro Kernel

## Public Runtime Status / حالة تشغيل النسخة العامة

**Status:** Public runtime readiness verified.
**الحالة:** تم التحقق من جاهزية تشغيل النسخة العامة.

The public repository is a sanitized, runnable edition of **Processual Maestro Kernel v2.0.0**. It is designed for external technical review, local runtime testing, and limited pilot evaluation without exposing the private development repository.

الريبو العام هو نسخة منقّحة وقابلة للتشغيل من **Processual Maestro Kernel v2.0.0**، مخصّصة للمراجعة التقنية الخارجية، والاختبار المحلي، والتقييم التجريبي المحدود دون كشف الريبو الخاص.

### Verified public runtime proof

A bilingual readiness proof is available here:

* [`docs/PUBLIC_RUNTIME_PROOF_AR_EN.md`](docs/PUBLIC_RUNTIME_PROOF_AR_EN.md)

This proof documents:

* successful FastAPI import from the public repository;
* local server startup with Uvicorn;
* working OpenAPI/Swagger documentation;
* working `X-API-Key` protection;
* working `/adapters/status`;
* working `/cgt/govern/status`;
* OpenCode configured as the default local provider;
* external providers intentionally left unconfigured until real keys are provided.

يوثق إثبات الجاهزية:

* نجاح استيراد تطبيق FastAPI من الريبو العام؛
* تشغيل السيرفر محليًا عبر Uvicorn؛
* ظهور OpenAPI/Swagger؛
* عمل الحماية عبر `X-API-Key`؛
* عمل `/adapters/status`؛
* عمل `/cgt/govern/status`؛
* تفعيل OpenCode كمزود محلي افتراضي؛
* بقاء المزودين الخارجيين غير مفعّلين إلى حين ضبط مفاتيح حقيقية.

### Public repository scope

The public/private separation is documented here:

* [`docs/REPOSITORY_SCOPE_AR.md`](docs/REPOSITORY_SCOPE_AR.md)

The public repository intentionally excludes private development material such as internal tests, private CGT modules, local runtime data, private handoff reports, `.env` files, and real API keys.

### External pilot message

A trilingual pilot message for external technical contacts is available here:

* [`docs/EXTERNAL_PILOT_MESSAGE_AR_EN_FR.md`](docs/EXTERNAL_PILOT_MESSAGE_AR_EN_FR.md)

### Client demo and limited pilot guide

A bilingual guide for running a controlled client-facing demo or a limited local pilot is available here:

* [`docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md`](docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md)

This guide explains how to present the public runtime to an external technical contact without exposing the private repository, real API keys, internal tests, or private runtime data.

### دليل عرض العميل والتجربة المحدودة

يتوفر دليل ثنائي اللغة لتنفيذ عرض مضبوط أمام عميل أو تجربة محلية محدودة هنا:

* [`docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md`](docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md)

يشرح هذا الدليل كيفية عرض النسخة العامة لجهة تقنية خارجية دون كشف الريبو الخاص أو مفاتيح API الحقيقية أو الاختبارات الداخلية أو بيانات التشغيل الخاصة.


### Quick local runtime check

From the public repository root:

```powershell
$env:API_KEYS="dev-public-test-key"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/adapters/status
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/cgt/govern/status
```

Swagger/OpenAPI UI:

```text
http://127.0.0.1:8000/docs
```

### Production note

The local test key above is only for development. Before any production deployment, configure strong environment variables such as:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

Never commit `.env` files or real provider API keys to GitHub.

---


### Production environment template

For production deployment, use:

```bash
cp .env.production.example .env
```

Then replace all placeholder values before starting the server.

The production template includes:

```text
ENVIRONMENT=production
APP_ENV=production
API_DEBUG=false
JWT_SECRET
API_KEYS
PROCESSUAL_CRYPTO_KEY_B64
CORS_ORIGINS
DATABASE_URL
POSTGRES_PASSWORD
REDIS_URL
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

It also documents optional production integrations:

```text
SENTRY_DSN
SENTRY_ENVIRONMENT
DISCORD_WEBHOOK_URL
DISCORD_ADMIN_WEBHOOK_URL
LEMONSQUEEZY_API_KEY
LEMONSQUEEZY_STORE_ID
LEMONSQUEEZY_WEBHOOK_SECRET
OPENROUTER_API_KEY
OPENCODE_API_URL
GENERIC_OPENAI_API_URL
```

Provider keys are customer-owned. Processual Maestro does not ship real OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, OpenCode, Ollama, vLLM, LM Studio, or generic OpenAI-compatible credentials. Each deploying organization must configure its own provider keys and endpoints.



### Extended production environment variables

The deployment must be aligned with `.env.production.example`.

In addition to the core values, production deployments must review the following variables:

| Variable                            |           Required | Purpose                                                                               |
| ----------------------------------- | -----------------: | ------------------------------------------------------------------------------------- |
| `ENVIRONMENT`                       |                Yes | Must be `production` for production startup validation.                               |
| `APP_ENV`                           |                Yes | Must be `production` to disable development-only API key fallback behavior.           |
| `API_DEBUG`                         |                Yes | Must be `false` in production.                                                        |
| `PROCESSUAL_CRYPTO_KEY_B64`         |                Yes | Base64-encoded 32-byte encryption key for stored sensitive provider/API-key material. |
| `SENTRY_DSN`                        |                 No | Enables Sentry error reporting.                                                       |
| `SENTRY_ENVIRONMENT`                |                 No | Should be `production` for production Sentry events.                                  |
| `SENTRY_TRACES_SAMPLE_RATE`         |                 No | Controls Sentry tracing sample rate.                                                  |
| `DISCORD_WEBHOOK_URL`               |                 No | Optional client-facing Discord notification webhook.                                  |
| `DISCORD_ADMIN_WEBHOOK_URL`         |                 No | Optional admin/operations Discord notification webhook.                               |
| `DISCORD_RATE_LIMIT_SECONDS`        |                 No | Minimum interval between Discord notifications.                                       |
| `LEMONSQUEEZY_API_KEY`              | If billing enabled | Lemon Squeezy API key.                                                                |
| `LEMONSQUEEZY_STORE_ID`             | If billing enabled | Lemon Squeezy store ID.                                                               |
| `LEMONSQUEEZY_WEBHOOK_SECRET`       | If billing enabled | Webhook signing secret.                                                               |
| `LEMONSQUEEZY_CHECKOUT_SUCCESS_URL` | If billing enabled | Production checkout success URL.                                                      |
| `LEMONSQUEEZY_CHECKOUT_CANCEL_URL`  | If billing enabled | Production checkout cancel URL.                                                       |
| `OPENROUTER_API_KEY`                |            If used | Customer-owned OpenRouter API key.                                                    |
| `OPENROUTER_API_URL`                |            If used | OpenRouter-compatible API base URL.                                                   |
| `OPENCODE_API_URL`                  |            If used | Local or private OpenCode/Ollama-compatible endpoint.                                 |
| `OPENCODE_API_KEY`                  |            If used | Customer-owned OpenCode-compatible API key or local placeholder where appropriate.    |
| `GENERIC_OPENAI_API_KEY`            |            If used | Customer-owned key for a generic OpenAI-compatible provider.                          |
| `GENERIC_OPENAI_API_URL`            |            If used | Generic OpenAI-compatible endpoint.                                                   |

Provider credentials are not bundled with Processual Maestro. The deploying customer or organization is responsible for its own provider keys, endpoints, billing, usage limits, and third-party provider availability.

Do not use documentation sample values in production. Replace every placeholder in `.env.production.example` and store real secrets through `.env`, Docker secrets, Kubernetes secrets, Google Secret Manager, or an equivalent secret-management system.







**Processual Maestro** is an adaptive governance middleware for AI agent workflows. It sits above any agent runtime (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK) and provides CGT v2 evaluation, safety guardrails, audit trails, and certifiable orchestration.

```text
User Goal
  → WorkflowPlan → TaskProfile → PolicyProfile → TempoPlan
  → Agent/Edge/Workflow Ψ observations
  → Adaptive cycle: checkpoint + drift scan + handoff advice
    + repair plan + policy critique
  → Quality gates: outcome coverage + patch success
    + false retry checks + handoff failure checks
  → Counterfactual replay: early escalation, policy swap,
    mediator insertion
  → Operating contract validation + convergence monitoring
  → Evidence integrity + adaptive certification
  → Runtime command bridge + outcome sweeps
  → Efficiency guardrails + workload budgets
  → Final adaptive review + certification + recommendations
```

## Features

- **CGT v2 Evaluation** — Computational Governance Trace with fate vectors, possibility mapping, and regime classification
- **Adaptive Governance Toolkit** — Policy selection, drift detection, checkpoint control, certification ladder, replay lab
- **Maestro Console** — Full SPA frontend with 11 pages (Overview, CGT, Workflows, Governance, Telemetry, Reports, Governor, Gateway, Simulation, Adapters, Settings)
- **CGT Governor** — LLM-powered governance with 5 adapters (OpenAI, Anthropic, Gemini, DeepSeek, OpenCode)
- **Gateway Engine** — Agent lifecycle management with policy enforcement and reward tracking
- **Simulation Engine** — Multi-agent scenario simulation with configurable agents and environments
- **Billing Integration** — Lemon Squeezy checkout, customer portal, webhook handling
- **Observability** — Prometheus metrics, Sentry error tracking, Discord notifications (client + admin channels)
- **Security** — JWT auth, API key management, AES-256-GCM encryption, rate limiting, audit logging, security headers
- **Infrastructure** — PostgreSQL, Redis, Docker Compose, Kubernetes manifests, Grafana dashboards

## Project Structure

```
processual_maestro_kernel/
├── processual_api/         # FastAPI backend (10 routers, 7 middleware)
├── processual_kernel/      # Core kernel (adaptive toolkit, security, observability)
├── cgtlib/                 # CGT math library (fate vectors, gates, invariants)
├── tests/                  # 957 tests — 952 pass, 0 fail
├── ops/                    # Docker, Grafana, Prometheus, K8s
├── docs/                   # Architecture, security, operations docs
└── examples/               # Basic usage, adaptive workflow, maestro workflow
```

## Quick Start

### Prerequisites

- Python ≥ 3.14
- PostgreSQL 16+ (optional, for database features)
- Redis 7+ (optional, for caching and rate limiting)

### Installation

```bash
cd processual_maestro_kernel
python -m pip install -e .[dev,api,observability,security,database,cache,reports,llm]
```

### Configuration

Copy the environment template:

```bash
cp .env.example .env
```

Edit `.env` with your settings. Minimum required:

```
JWT_SECRET=your-secret-key
ENVIRONMENT=development
```

### Run

```bash
uvicorn processual_api.main:app --reload
```

Open http://localhost:8000 in your browser.

### Run Tests

```bash
python -m pytest -q
```

## API Overview

| Router       | Prefix              | Endpoints                             |
|-------------|---------------------|---------------------------------------|
| Health      | `GET /health/live`, `GET /health/ready` | |
| Auth        | `/auth`             | `POST token`, `POST api-key`, `GET me` |
| CGT         | `/cgt`              | `POST evaluate`                       |
| Workflows   | `/workflows`        | `POST create`, `GET get`, `POST checkpoint`, `GET governance` |
| Governance  | `/governance`       | `GET status`                          |
| Telemetry   | `/telemetry`        | `POST ingest` (auth required)         |
| Reports     | `/reports`          | `POST fate`, `POST generate-llm`      |
| Discord     | `/discord`          | `POST webhook/test`, `POST webhook/test-admin` |
| CGT Governor| `/cgt/govern`       | `POST govern`, `POST batch`, `GET status`, `POST toggle`, `GET reports` (filtered+paged), `GET reports/export` (JSON download), `POST repair`, `POST auto-repair`, `POST compare`, `POST report`, `GET reports/pdf`, `GET reports/{eval_id}/pdf`, `POST simulate`, `GET simulate/reports`, `GET simulate/reports/{sim_id}/pdf` |
|             | `/cgt/analyze`      | `POST analyze`                        |
|             | `/cgt/govern/gateway` | `POST evaluate`, `GET/POST agents`, `GET agents/{id}`, `POST agents/{id}/action`, `GET agents/{id}/trend`, `GET dashboard`, `GET reports/pdf` |
|             | `/adapters`         | `GET status`, `POST configure`, `POST test` |
| Settings    | `/settings`         | `GET general`, `PUT general`, `PUT/DELETE llm-provider`, `POST llm-provider/test`, `PUT notifications`, `POST notifications/test`, `GET subscription`, `GET/POST/DELETE api-keys` |
| Applications| `/applications`     | `POST create`, `GET pending`, `GET all`, `GET {id}`, `POST {id}/review`, `GET {id}/demo`, `GET demo/check/{id}`, `POST demo/{id}/increment` |
| Billing     | `/billing`          | `POST checkout`, `GET portal`, `POST webhook`, `GET subscription` |
| —           | `/metrics`          | Prometheus metrics                    |
| —           | `/`                 | Splash page HTML                      |
| —           | `/login`            | Login page HTML                       |

## Docker

```bash
docker compose up --build
```

This starts: API server, PostgreSQL, Redis, Prometheus, Grafana.

## Kubernetes

Deploy to K8s with the provided manifests:

```bash
kubectl apply -k ops/k8s/overlays/dev/
```

## Philosophy

- The kernel decides.
- The toolkit reviews, suggests, and improves around the kernel.
- The runtime executes.
- Every decision is auditable with a policy version and unique ID.

## License

MIT

## Cloud Run readiness

The container is Cloud Run ready: it binds Uvicorn to `${PORT:-8000}`, keeps the live health check on `/health/live`, and exposes readiness through `/health/ready`.

Required production environment values remain explicit and must not use local defaults:

- `JWT_SECRET`
- `DATABASE_URL`
- `REDIS_URL`
- `MAESTRO_ADMIN_EMAIL`
- `MAESTRO_ADMIN_PASSWORD`

Billing remains BYOK: provider costs are not included in Processual Maestro pricing.

## Cloud Run deploy contract

Processual Maestro is Cloud Run-ready, but deployment is intentionally an explicit operator step. The repository-level Cloud Build contract builds and publishes the container image; it does not deploy the service automatically.

Build the image with Cloud Build:

```powershell
gcloud builds submit --config cloudbuild.yaml --substitutions _REGION=us-central1,_REPOSITORY=processual-maestro,_SERVICE=processual-maestro-api
```

Deploy the already-built image only after production secrets and environment variables are configured:

```powershell
gcloud run deploy processual-maestro-api --image us-central1-docker.pkg.dev/PROJECT_ID/processual-maestro/processual-maestro-api:latest --region us-central1 --platform managed --allow-unauthenticated --port 8000 --set-env-vars ENVIRONMENT=production,APP_ENV=production,API_DEBUG=false --set-secrets JWT_SECRET=JWT_SECRET:latest,API_KEYS=API_KEYS:latest,PROCESSUAL_CRYPTO_KEY_B64=PROCESSUAL_CRYPTO_KEY_B64:latest,DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,MAESTRO_ADMIN_EMAIL=MAESTRO_ADMIN_EMAIL:latest,MAESTRO_ADMIN_PASSWORD=MAESTRO_ADMIN_PASSWORD:latest,POSTGRES_PASSWORD=POSTGRES_PASSWORD:latest,REDIS_PASSWORD=REDIS_PASSWORD:latest,GRAFANA_ADMIN_PASSWORD=GRAFANA_ADMIN_PASSWORD:latest
```

Cloud Run provides the runtime `PORT` value. The container keeps the default fallback `${PORT:-8000}` for local compatibility.

Live health check:

```text
/health/live
```

Readiness check:

```text
/health/ready
```

### Required production environment matrix

| Variable | Required for Cloud Run | Delivery | Notes |
| --- | --- | --- | --- |
| `ENVIRONMENT` | Yes | env var | Set to `production` for production deployment checks. |
| `JWT_SECRET` | Yes | Secret Manager | Must be strong and unique. Never use `CHANGE_ME_IN_PRODUCTION`. |
| `API_KEYS` | Yes | Secret Manager | Strong service/API bootstrap key. Do not use development fallback keys. |
| `PROCESSUAL_CRYPTO_KEY_B64` | Yes | Secret Manager | Base64-encoded 32-byte encryption key for protected secrets. |
| `DATABASE_URL` | Yes | Secret Manager | Production database connection string. |
| `REDIS_URL` | Yes | Secret Manager | Production Redis connection string. |
| `MAESTRO_ADMIN_EMAIL` | Yes | Secret Manager | Initial admin login identity. |
| `MAESTRO_ADMIN_PASSWORD` | Yes | Secret Manager | Initial admin login secret. |
| `POSTGRES_PASSWORD` | Yes | Secret Manager | Required by the current production startup gate; use a strong value even when the database provider is external. |
| `REDIS_PASSWORD` | Yes | Secret Manager | Required by the current production startup gate; keep aligned with the deployed Redis provider. |
| `GRAFANA_ADMIN_PASSWORD` | Yes | Secret Manager | Required by the current production startup gate; keep a strong secret even for API-only deployments. |

Billing remains BYOK: provider costs are not included in Maestro usage pricing, and plan allowances must come from the pricing catalog rather than deployment configuration.

### Production secrets contract

The Cloud Run deploy command must map every production secret through Secret Manager. Do not place real secret values in `cloudbuild.yaml`, README examples, static assets, tests, or committed `.env` files.

The canonical production secret names are maintained in `processual_api/settings.py` as `PRODUCTION_SECRET_ENV_VARS`; documentation and regression tests must stay aligned with that contract.

## Subscription pricing catalog

Processual Maestro currently uses a draft subscription pricing catalog.

- Pricing status: draft.
- Billing policy: BYOK.
- Provider costs are not included.
- Monthly Maestro unit allowances are resolved from the usage pricing catalog.
- Lemon Squeezy checkout is not considered production-ready until approved plan prices and variant IDs are mapped to the subscription catalog.
