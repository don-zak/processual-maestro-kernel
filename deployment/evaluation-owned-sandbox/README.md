# Project-Owned Evaluation Sandbox

This workload is a deliberately minimal, project-owned, read-only HTTPS sandbox target for External Evaluation qualification.

## Runtime contract

- The hosting platform terminates HTTPS and forwards traffic to this container on `PORT`.
- `GET /health/live` returns service health metadata.
- `GET /users/1` returns deterministic non-production customer-shaped JSON.
- `POST`, `PUT`, `PATCH`, and `DELETE` fail closed with HTTP 405.
- The service requires no credentials and stores no request bodies, headers, secrets, or customer data.
- `production_allowed` is always false.

## Render Blueprint deployment

The repository root contains `render.yaml`. It defines one Docker web service using only this sandbox directory as the Docker build context:

- service: `processual-maestro-evaluation-sandbox`
- Dockerfile: `deployment/evaluation-owned-sandbox/Dockerfile`
- Docker context: `deployment/evaluation-owned-sandbox`
- health check: `GET /health/live`
- no secret environment variables are declared in the Blueprint

In Render, create a Blueprint from this repository and review the proposed service before applying it. Keep the generated Render HTTPS hostname dedicated to this project-owned evaluation sandbox. After deployment, verify both `/health/live` and `/users/1` over HTTPS before provisioning the hostname into a Maestro Evaluation binding.

Do not treat successful Blueprint parsing as operational proof. Final proof requires a deployed revision and real HTTPS requests from the qualified Maestro runtime.

## Cloud Run deployment (alternative)

```powershell
gcloud builds submit deployment/evaluation-owned-sandbox `
  --tag REGION-docker.pkg.dev/PROJECT_ID/processual-maestro/evaluation-owned-sandbox:latest

gcloud run deploy processual-maestro-evaluation-sandbox `
  --image REGION-docker.pkg.dev/PROJECT_ID/processual-maestro/evaluation-owned-sandbox:latest `
  --region REGION `
  --platform managed `
  --allow-unauthenticated `
  --port 8080 `
  --min-instances 0 `
  --max-instances 2
```

After deployment, record the HTTPS service URL and use only that project-owned URL when producing the final External Evaluation operational proof. Do not mark `customer_owned` or `project_owned` true when using third-party endpoints.

## Qualification proof

A valid final proof must demonstrate, on one immutable Maestro SHA and one deployed sandbox revision:

1. HTTPS `GET /health/live` succeeds.
2. HTTPS `GET /users/1` succeeds and returns the deterministic sandbox payload.
3. Maestro provisions the binding to the owned hostname.
4. `POST /evaluation/runtime/task-execute` performs a real outbound request.
5. Same idempotency key replays without a second side effect.
6. Same idempotency key with different input returns conflict.
7. Revoked/expired Evaluation authority is rejected.
8. Evidence contains hashes/metadata only; no raw secret or raw task input is persisted.

A local/unit test, a parsed Blueprint, or a third-party endpoint is not sufficient to claim the final owned live proof.
