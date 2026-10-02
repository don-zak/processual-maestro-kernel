# External Evaluation Operational Runbook

This runbook defines the operator sequence for project-owned Render qualification and customer-owned sandbox onboarding.

## 1. Project-owned Render qualification

Use one immutable Maestro commit SHA and one immutable project-owned sandbox deployment revision. They do not need to be the same Git SHA, but both exact revisions must be recorded in the qualification evidence.

Required proof:

1. Authority/runtime service is Live on the exact intended Maestro qualification SHA.
2. Project-owned sandbox service is Live on a recorded immutable sandbox revision.
3. The owned sandbox Docker context is `deployment/evaluation-owned-sandbox` only.
4. HTTPS `GET /health/live` succeeds on the owned sandbox.
5. HTTPS `GET /users/1` returns the deterministic synthetic payload.
6. No production/customer secrets are configured for the public owned sandbox.
7. In Admin → External Evaluation, run **Owned CRM proof preset** for `CRM-CONTEXT-01` using the exact owned sandbox HTTPS base URL.
8. The preset must complete: prepared CRM read binding → project-owned synthetic content contract → project-scoped anonymous/public credential reference → short-lived sandbox execution grant → hardened live proof → binding catalog readiness recheck.
9. The preset is successful only when the resulting binding reports `selectable=true`, `sandbox_ready`, live network execution, verified peer address, valid response mapping, and `production_allowed=false`.
10. The preset itself must not create an Evaluation Grant or API key.
11. A bounded Evaluation Grant includes the exact task, binding, endpoint and derived scopes.
12. Explicit CRM grant has 100 admitted-execution units; explicit Integration grant has 200.
13. First unique idempotency claim consumes exactly one unit.
14. Durable replay consumes zero additional units.
15. Same idempotency key with changed input returns 409 without consuming another unit.
16. Individual key revocation causes immediate runtime rejection.
17. Grant revocation rejects all linked keys.
18. Evidence includes hashes/metadata and excludes raw API key and raw task input.
19. The customer dashboard shows current grant/key metadata, quota progress, execution stage, grant-authoritative guided scenarios and customer-safe receipt.
20. The administrator receives the aggregate final audit summary with `qualification_decision=operator_required` and no automatic pass/fail verdict.

Do not claim operational completion from Blueprint validation, unit tests, a prepared binding without live proof, or a browser-only readiness state.

## 2. Qualification experiment matrix

### Q1 — Exact-head runtime and owned-sandbox readiness

Live Render proof, zero evaluation quota:

- record exact Maestro Git commit SHA and confirm that same SHA is Live on the authority service
- record exact project-owned sandbox deploy/revision separately
- authority startup/migrations/bootstrap complete
- authority `GET /health/live` succeeds
- owned sandbox `GET /health/live` succeeds
- owned sandbox `GET /users/1` returns only deterministic synthetic data
- no customer or production credential material is required by the owned sandbox

### Q2 — Owned CRM preset, Grant authority and key handoff

Live administrator flow, zero execution quota until the customer task is admitted:

1. In External Evaluation, run **Prepare & prove CRM-CONTEXT-01** using the project-owned sandbox base URL.
2. Verify the preset reports the prepared binding as `selectable=true` and sandbox readiness as `sandbox_ready`.
3. Verify proof reports real network execution, verified peer address, valid mapping and readiness for task consumption.
4. Verify content ownership is `project`, credential reference scope is `project`, anonymous/public access contains no secret material, and production is disabled.
5. Refresh the authoritative binding catalog and select only the resulting CRM binding.
6. Select canonical task `crm.customer_context` and endpoint `POST /evaluation/runtime/task-execute`.
7. Create one explicitly selected `CRM` grant for this first proof.
8. Verify the persisted grant remains explicitly CRM; runtime/binding shape must not silently change its type.
9. Verify CRM quota is derived as `100` admitted executions and is not manually overridable.
10. Issue one raw API key; raw secret is visible only once.
11. Copy the separate safe customer handoff text.
12. Confirm key delivery, then confirm receipt.
13. Verify lifecycle `issued -> delivery_confirmed -> acknowledged`.

The API key requires no subscription, registration or commercial quota. The grant is the authority for type, tasks, bindings, endpoints, expiry and evaluation quota. The preset prepares/proves a binding only and cannot create or widen Grant authority.

### Q3 — Customer status/dashboard

Live customer flow, zero execution quota:

- connect with the issued evaluation key
- status/dashboard read succeeds
- verify Grant ID, safe key identifier/prefix, explicit evaluation type, expiry, authorized tasks/bindings and quota values
- verify `guided_scenarios` comes from backend status authority rather than a client-owned catalog
- verify `CRM-CONTEXT-01` is shown runnable only for the sealed CRM task/binding/runtime endpoint
- verify no raw key is persisted in browser storage or evidence
- verify `production_allowed=false`

### Q4 — New admitted execution

Live customer flow, consumes exactly **1** unit:

- prepare `CRM-CONTEXT-01` from the backend-authoritative guided scenario
- submit one synthetic task using a fresh idempotency key
- verify admission is recorded once
- verify quota changes from `0/100` to `1/100 used` and remaining from `100` to `99`
- verify progress reaches `Admitted -> Executing -> Outcome -> Evidence persisted`
- verify evidence omits raw API key and raw task input
- verify both customer-safe execution receipt and administrator audit view refer to the same execution identity

### Q5 — Durable replay

Live customer flow, consumes **0 additional** units:

- resend the exact same task, input and idempotency key from Q4
- verify the durable response is replayed
- verify usage remains `1/100` and remaining remains `99`
- verify replay does not dispatch a second downstream execution

### Q6 — Idempotency conflict

Live customer flow, consumes **0 additional** units:

- reuse the Q4 idempotency key with changed input
- expect HTTP `409`
- verify usage remains `1/100` and remaining remains `99`
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
- verify owned-sandbox proof metadata remains safe and does not contain raw external response, raw task input or credential material
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

## 4. Project-owned preset contract

The first live proof uses the project-owned preset `CRM-CONTEXT-01`.

The operator supplies only:

- project-owned public HTTPS sandbox base URL
- optional stable binding ID
- bounded sandbox-grant TTL between 5 and 120 minutes

The preset may prepare and prove only:

- adapter contract `crm`
- canonical task `crm.customer_context`
- read-only `GET /users/1`
- required scope `crm:read`
- canonical response mapping into the CRM context task
- project-owned synthetic content references
- project-scoped `anonymous/public` credential reference with no credential value
- short-lived sandbox execution grant
- hardened live proof and authoritative binding-catalog recheck

The preset must never:

- issue an Evaluation Grant
- issue or expose an Evaluation API key
- add tasks/endpoints/scopes outside the fixed CRM preset
- write production data
- store raw external response payloads, request bodies or secrets as qualification evidence
- claim success when the authoritative binding catalog is not `selectable=true`

## 5. Customer-owned sandbox onboarding

Customer-owned sandbox qualification is a later onboarding phase and must remain separate from the project-owned proof.

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

## 6. Quota semantics

Quota measures **new admitted executions**.

- successful API-key authentication: 0 units
- status/dashboard reads: 0 units
- scenario discovery through customer status: 0 units
- authorization/configuration rejection before claim: 0 units
- new transactional execution claim: 1 unit
- durable replay: 0 additional units
- idempotency conflict before a new claim: 0 additional units
- admitted execution with later uncertain/failed network outcome: remains 1 consumed unit

This placement prevents authentication probing and invalid task/binding requests from spending customer evaluation capacity, while preserving accounting for an operation that reached the execution boundary.

## 7. Incident response

If a key is suspected compromised:

1. revoke the individual key immediately
2. verify runtime rejection with the revoked key
3. inspect evidence by key ID/prefix only; never request the raw key
4. issue a replacement key under the same grant if the grant remains trusted and within policy
5. revoke the entire grant when task/binding/recipient authority is no longer trusted

## 8. Completion gate

External Evaluation is ready for a customer only when:

- CI is green on the exact intended head
- the same exact Maestro head is Live on the authority service
- the project-owned sandbox revision used for proof is recorded and remains immutable for the evidence set
- the owned CRM preset has produced a `selectable=true` sandbox-ready binding from a real hardened live proof
- Q1 through Q9 have the required live proof, using only bounded synthetic executions
- Q10 is green in the isolated PostgreSQL integration qualification
- the customer dashboard and safe handoff match the authoritative grant contract
- administrator final audit remains operator-controlled
- superseded UI/assets are isolated from active loaders; broad deletion/deprecation cleanup remains governed by `docs/FINAL_LAUNCH_TODO.md`

Customer-owned sandbox qualification is a second phase and must not be used to substitute for the project-owned sandbox proof.
