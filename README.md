# Processual Maestro Kernel

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
