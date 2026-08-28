# Processual Maestro — Portable Evaluation Runtime

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

The launcher creates `.env.evaluation` locally, builds the public evaluation image, starts PostgreSQL/Redis/API, waits for health, then opens the API documentation in the browser.

Useful commands:

```powershell
.\CHECK-STATUS.ps1
.\STOP-MAESTRO.ps1
.\RESET-DEMO.ps1 -Force
```

## Linux / macOS

Requirements: Docker with Docker Compose, `curl`, `od`, `xxd`, and `base64`.

```bash
chmod +x start-maestro.sh
./start-maestro.sh
```

## Endpoints

- Product/API root: http://localhost:8000
- Health: http://localhost:8000/health/live
- API docs: http://localhost:8000/docs

## What this proves

The portable runtime lets a reviewer launch the product locally without access to production infrastructure or private repositories. It is a POC/evaluation distribution, not a production deployment and not evidence that production-only commercial gates are open.

## Distribution integrity

When shipped as an evaluation archive, keep the release manifest and SHA-256 checksum next to the ZIP. Build the archive only from a pinned, qualified Git SHA.
