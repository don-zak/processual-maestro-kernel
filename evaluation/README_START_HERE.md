# Processual Maestro — Startup Tunisia Evaluation Edition

This package is a self-contained evaluation edition intended for reviewers and technical demonstrations. It runs the public Processual Maestro image with local PostgreSQL and Redis through Docker Compose.

## Safety boundary

The bundle is evaluation-only:

- no production secrets are included;
- local secrets are generated on first start;
- private `cgtlib/private` code is not included in the public Docker target;
- Lemon Squeezy and real billing credentials are absent;
- Tunisia local top-up is disabled by default;
- external LLM execution is disabled by default;
- only synthetic/demo data should be used.

## Windows / PowerShell

Requirements: Docker Desktop with Docker Compose.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\START-MAESTRO.ps1
```

The launcher creates `.env.evaluation` locally, starts PostgreSQL/Redis/API, waits for health, then opens `EVALUATION_HOME.html`, the guided reviewer entry point.

Useful commands:

```powershell
.\SHOW-EVALUATION-ACCESS.ps1
.\SHOW-EVALUATION-ACCESS.ps1 -ShowSecrets
.\RUN-GUIDED-DEMO.ps1
.\CHECK-STATUS.ps1
.\STOP-MAESTRO.ps1
.\RESET-DEMO.ps1 -Force
```

`SHOW-EVALUATION-ACCESS.ps1` hides generated local secrets by default. Use `-ShowSecrets` only on the evaluator machine when the local admin password or API key must be copied into the product UI.

`RUN-GUIDED-DEMO.ps1` checks runtime health and opens both the reviewer home and the recorded governance evidence page.

## Linux / macOS

Requirements: Docker with Docker Compose, `curl`, `od`, `xxd`, and `base64`.

```bash
chmod +x start-maestro.sh
./start-maestro.sh
```

## Reviewer entry points

- Evaluation home: `EVALUATION_HOME.html`
- Recorded governance evidence: `RECORDED-GOVERNANCE-EVIDENCE.html`
- Product / Console: http://localhost:8000/console
- Admin workspace: http://localhost:8000/admin
- Product/API root: http://localhost:8000
- Health: http://localhost:8000/health/live
- API docs: http://localhost:8000/docs

## Recommended Startup Tunisia walkthrough

Read `GUIDED-DEMO.md` and use the synthetic **Enterprise Incident / Ticket Governance** scenario. The intended story is:

`controlled input -> identity/authority -> entitlement/quota -> runtime governance -> recorded governance evidence -> human validation -> audit/evidence`

The purpose is to demonstrate that Maestro is not merely an agent builder: authorization is separated from execution, commercial/runtime controls influence execution, governance participates in the lifecycle and important decisions remain auditable.

## Recorded governance evidence

The public portable image deliberately excludes the private CGT implementation. To keep the reviewer package useful without leaking that boundary or requiring an external model key, the bundle includes `RECORDED-GOVERNANCE-EVIDENCE.html`.

That page replays the outcome of a previously verified local Docker/Ollama governance proof (`multi_agent_v1_1780450078`) and shows the recorded agent lifecycle plus rank/reward/policy/action results. It is deterministic recorded evidence, not a live provider call and not Production evidence.

## What this proves

The portable runtime lets a reviewer launch the product locally without access to production infrastructure or private repositories. It is a POC/evaluation distribution, not a production deployment and not evidence that production-only commercial gates are open.

The evaluation edition deliberately separates what is demonstrable locally from what still requires a controlled client POC or Production qualification.

## Distribution integrity

When shipped as an evaluation archive, keep the release manifest and SHA-256 checksum next to the ZIP. Build the archive only from a pinned, qualified Git SHA.
