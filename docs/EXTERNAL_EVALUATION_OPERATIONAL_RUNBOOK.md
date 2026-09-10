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
12. Same idempotency key with changed input returns 409 without consuming another unit.
13. Individual key revocation causes immediate runtime rejection.
14. Grant revocation rejects all linked keys.
15. Evidence includes hashes/metadata and excludes raw API key and raw task input.
16. The customer dashboard shows current grant/key metadata, quota progress, execution stage and customer-safe receipt.
17. The administrator receives the aggregate final audit summary with `qualification_decision=operator_required` and no automatic pass/fail verdict.

Do not claim operational completion from Blueprint validation or unit tests alone.

## 2. Qualification experiment matrix

### Q1 — Exact-head runtime readiness

Live Render proof, zero evaluation quota:

- exact Git commit equals the intended qualification head
- deployment status is Live
- startup/migrations/bootstrap complete
- `GET /health/live` succeeds
- owned sandbox `GET /users/1` returns only deterministic synthetic data

### Q2 — Grant authority and key handoff

Live administrator flow, zero execution quota:

- create one explicitly selected `CRM` or `Integration` grant
- verify the persisted grant reports that exact type; task/binding shape must not silently change an explicit grant type
- verify quota is derived from type: CRM `100`, Integration `200`
- issue one raw API key; raw secret is visible only once
- copy the separate safe customer handoff text
- confirm delivery, then confirm receipt
- verify lifecycle `issued -> delivery_confirmed -> acknowledged`

The API key requires no subscription, registration or commercial quota. The grant is the authority for type, tasks, bindings, endpoints, expiry and evaluation quota.

### Q3 — Customer status/dashboard

Live customer flow, zero execution quota:

- connect with the issued evaluation key
- status/dashboard read succeeds
- verify Grant ID, safe key identifier/prefix, evaluation type, expiry, authorized tasks/bindings and quota values
- verify no raw key is persisted in browser storage or evidence
- verify `production_allowed=false`

### Q4 — New admitted execution

Live customer flow, consumes exactly **1** unit:

- submit one synthetic task using a fresh idempotency key
- verify admission is recorded once
- verify quota changes by exactly `+1 used / -1 remaining`
- verify progress reaches an outcome and persisted evidence
- verify evidence omits raw API key and raw task input
- verify both customer-safe execution receipt and administrator audit view refer to the same execution identity

### Q5 — Durable replay

Live customer flow, consumes **0 additional** units:

- resend the exact same task, input and idempotency key
- verify the durable response is replayed
- verify usage count and remaining quota are unchanged
- verify replay does not dispatch a second downstream execution

### Q6 — Idempotency conflict

Live customer flow, consumes **0 additional** units:

- reuse the Q4 idempotency key with changed input
- expect HTTP `409`
- verify quota remains unchanged
- verify no second downstream execution is admitted

### Q7 — Individual key revocation

Live administrator/customer flow, zero execution quota after revocation:

- if sibling-key isolation is being qualified, issue a second key under the same grant before revocation
- revoke only the target key
- verify the revoked key is rejected immediately by status/runtime authorization
- when a sibling key exists, verify it remains valid

### Q8 — Grant revocation

Live administrator/customer flow, zero execution quota after revocation:

- revoke the grant
- verify every linked key is rejected
- verify no revoked credential can reach admission or evidence creation

### Q9 — Final audit

Live administrator flow, zero execution quota:

- generate/read `external_evaluation_final_summary`
- verify aggregate executions, replay/audit evidence, revocation state and per-key quota semantics
- verify `qualification_decision=operator_required`
- verify there is no automatic qualification verdict
- preserve a customer-safe receipt separately from administrator-only audit details

### Q10 — Quota exhaustion and concurrency safety

**Integration-test database only; do not burn a live customer/evaluator quota to exhaustion.**

- use a deliberately tiny test quota such as `1`
- race two claims and prove only one consumes the unit
- prove durable replay consumes `+0`
- prove a new claim after exhaustion returns HTTP `429`
- prove quota rejection telemetry is persisted
- prove same idempotency key with changed fingerprint remains a conflict

The PostgreSQL integration qualification is the authoritative destructive/concurrency proof for exhaustion. The live Render qualification must remain bounded and must not consume 100/200 executions merely to demonstrate `429`.

## 3. Key handoff

- issue raw key once
- deliver the key using a secret-capable channel
- send non-secret access metadata separately
- operator presses `Confirm Key Sent`
- customer confirms storage/receipt
- operator presses `Confirm Receipt`
- never paste the key into tickets, GitHub, logs or screenshots

Delivery acknowledgement is audit evidence only and does not activate or widen authority.

The safe handoff text should include the customer portal location, authentication header name, Grant ID, safe key ID/prefix, evaluation type, admitted-execution quota, expiry, allowed canonical tasks, prepared bindings, allowed endpoints, idempotency guidance, execution-stage expectations, zero-quota status/replay semantics, subscription-not-required status and production-disabled status. It must not contain the raw API key or another secret.

## 4. Customer-owned sandbox onboarding

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

## 5. Quota semantics

Quota measures **new admitted executions**.

- successful API-key authentication: 0 units
- status/dashboard reads: 0 units
- authorization/configuration rejection before claim: 0 units
- new transactional execution claim: 1 unit
- durable replay: 0 additional units
- idempotency conflict before a new claim: 0 additional units
- admitted execution with later uncertain/failed network outcome: remains 1 consumed unit

This placement prevents authentication probing and invalid task/binding requests from spending customer evaluation capacity, while preserving accounting for an operation that reached the execution boundary.

## 6. Incident response

If a key is suspected compromised:

1. revoke the individual key immediately
2. verify runtime rejection with the revoked key
3. inspect evidence by key ID/prefix only; never request the raw key
4. issue a replacement key under the same grant if the grant remains trusted and within policy
5. revoke the entire grant when task/binding/recipient authority is no longer trusted

## 7. Completion gate

External Evaluation is ready for a customer only when:

- CI is green on the exact intended head
- the same exact head is Live on the authority service
- Q1 through Q9 have the required live proof, using only bounded synthetic executions
- Q10 is green in the isolated PostgreSQL integration qualification
- the customer dashboard and safe handoff match the authoritative grant contract
- administrator final audit remains operator-controlled
- superseded UI/assets are isolated from active loaders; broad deletion/deprecation cleanup remains governed by `docs/FINAL_LAUNCH_TODO.md`

Customer-owned sandbox qualification is a second phase and must not be used to substitute for the owned-sandbox proof.
