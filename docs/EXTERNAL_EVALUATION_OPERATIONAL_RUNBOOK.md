# External Evaluation Operational Runbook

This runbook defines the operator sequence for project-owned Render qualification and customer-owned sandbox onboarding.

## 1. Project-owned Render qualification

Use one immutable Maestro commit SHA and one immutable Render deployment revision.

Required proof:

1. Render service is built from the repository `render.yaml` Blueprint.
2. Docker context is `deployment/evaluation-owned-sandbox` only.
3. HTTPS `GET /health/live` returns success.
4. HTTPS `GET /users/1` returns the deterministic synthetic payload.
5. No production/customer secrets are configured for the public owned sandbox.
6. The exact Render hostname is stored in the prepared Maestro sandbox binding.
7. The binding uses `anonymous/public` credential reference when the owned sandbox requires no authentication.
8. A bounded Evaluation Grant includes the exact task, binding, endpoint and scopes.
9. An Integration Evaluation key has 200 admitted-execution units; CRM has 100.
10. First unique idempotency claim consumes exactly one unit.
11. Durable replay consumes zero additional units.
12. Same idempotency key with changed input returns 409.
13. A new claim after quota exhaustion returns 429.
14. Individual key revocation causes immediate runtime rejection.
15. Evidence includes hashes/metadata and excludes raw API key and raw task input.

Do not claim operational completion from Blueprint validation or unit tests alone.

## 2. Key handoff

- issue raw key once
- deliver the key using a secret-capable channel
- send non-secret access metadata separately
- operator presses `Confirm Key Sent`
- customer confirms storage/receipt
- operator presses `Confirm Receipt`
- never paste the key into tickets, GitHub, logs or screenshots

Delivery acknowledgement is audit evidence only and does not activate or widen authority.

## 3. Customer-owned sandbox onboarding

Collect only the sandbox integration contract:

- public HTTPS sandbox base URL
- method/path
- canonical task and expected field mapping
- synthetic test identifiers
- success status codes
- timeout expectations
- authentication type
- technical contact

If authentication is required, create a dedicated short-lived sandbox credential and store only a secret reference in Maestro. Never store `Authorization`, `X-API-Key`, passwords, cookies, or production secrets inside the endpoint binding.

Start with one read-only task and one binding. Add draft or approval-gated write operations only after read-only qualification succeeds.

## 4. Quota semantics

Quota measures **new admitted executions**.

- successful API-key authentication: 0 units
- authorization/configuration rejection before claim: 0 units
- new transactional execution claim: 1 unit
- durable replay: 0 additional units
- admitted execution with later uncertain/failed network outcome: remains 1 consumed unit

This placement prevents authentication probing and invalid task/binding requests from spending customer evaluation capacity, while preserving accounting for an operation that reached the execution boundary.

## 5. Incident response

If a key is suspected compromised:

1. revoke the individual key immediately
2. verify runtime rejection with the revoked key
3. inspect evidence by key ID/prefix only; never request the raw key
4. issue a replacement key under the same grant if the grant remains trusted and within policy
5. revoke the entire grant when task/binding/recipient authority is no longer trusted

## 6. Completion gate

External Evaluation is ready for a customer only when CI is green and the live Render proof has been captured against the same intended Maestro revision. Customer-owned sandbox qualification is a second phase and must not be used to substitute for the owned-sandbox proof.
