# Portable Project-Owned Evaluation Sandbox

This directory contains a provider-neutral static deployment of the deterministic External Evaluation CRM proof target. It exists to keep `CRM-CONTEXT-01` independent of the current Render public edge while preserving the same read-only contract.

## Contract

- `GET /users/1` returns the project-owned synthetic CRM customer fixture.
- `GET /health/live` returns non-production service metadata.
- No credentials, request body, customer data, or production authority are required.
- The payload is immutable deployment content from this repository.
- The External Evaluation binding remains `GET /users/1`, `crm.customer_context`, `crm:read`, sandbox-only, success code `200`.
- No fallback changes a failed proof into a pass. The Maestro proof remains fail closed.

## Netlify

Create a site from this repository with base directory:

`deployment/evaluation-owned-sandbox-static`

The included `netlify.toml` publishes `public/` and rewrites the extensionless qualification routes.

## Vercel

Create a project from this repository with root directory:

`deployment/evaluation-owned-sandbox-static`

The included `vercel.json` rewrites the same qualification routes.

## Qualification

Before changing the Maestro preset URL, independently verify over HTTPS:

1. `/health/live` returns HTTP 200.
2. `/users/1` returns HTTP 200 and the deterministic synthetic object.
3. The hostname is the project-controlled deployment created from this repository.
4. The Maestro Authority performs exactly one live proof request per operator action.
5. A failed HTTP status remains a failed proof; no retry or alternate endpoint is hidden inside the Authority.

The old Render-owned sandbox can remain available as a diagnostic target, but it must not be used for qualification while its public edge returns HTTP 429 before the request reaches the sandbox application.
