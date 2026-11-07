# External Evaluation Client Guide

This guide is the customer-facing operating contract for non-production Maestro External Evaluation.

## What the customer receives

External Evaluation is subscription-independent. The customer does not need a paid plan, product subscription, registration entitlement, Render credentials, database credentials, administrator access, or production credentials.

The Platform Administrator first creates an authoritative Evaluation Grant. That grant — not the customer, browser UI, API key, sandbox, or commercial billing layer — defines:

- evaluation type: `crm` or `integration`
- admitted-execution quota
- expiry
- allowed canonical task IDs
- allowed prepared binding IDs
- allowed API endpoints and derived runtime scopes
- non-production execution boundary

The customer then receives a Maestro Evaluation API key bound to that grant. The raw key is displayed only once at issue time and must be stored in a secret manager or environment variable. The API key cannot expand or modify the grant authority.

## One-time API key handoff package

The raw API key is delivered separately from the safe technical handoff text. The handoff text should be generated beside the one-time key so the operator can send both through the approved delivery channel without manually reconstructing the evaluation contract.

The safe handoff text contains:

- Maestro External Evaluation portal/base URL
- header name: `X-API-Key`
- Evaluation Grant ID
- API Key ID and/or safe prefix
- evaluation type (`crm` or `integration`)
- admitted-execution quota and expiry
- allowed canonical task IDs
- allowed prepared binding IDs
- allowed API endpoints
- idempotency guidance
- expected execution/evidence stages
- explicit statement that subscription is not required
- explicit statement that production execution is disabled
- support/next-step guidance

The handoff text must not contain database credentials, Render credentials, provider secrets, sandbox credential material, key hashes, raw task inputs, production credentials, or any second secret. The one-time raw Evaluation API key is the only secret handed to the customer through this process.

## Customer data required to issue a key

No customer secret, password, production API key, billing information, subscription, or production dataset is required to generate the Maestro Evaluation key. The administrator needs only identification and grant-scope metadata such as `client_id`, `issued_to`, purpose, duration, tasks, endpoints, evaluation type, and prepared sandbox bindings.

If Maestro must call a customer-owned sandbox, its credential is a separate short-lived sandbox credential. The binding stores only a secret reference. Raw authentication headers must never be embedded in endpoint-binding settings.

## Authentication

Send the key in the `X-API-Key` header:

```bash
export MAESTRO_EVALUATION_API_KEY='pmk_...'
```

Never commit the key to source control, tickets, logs, screenshots, or persistent client-side browser storage.

## Customer dashboard

The bounded External Evaluation dashboard is available without Admin access and authenticates only with the Evaluation API key. The raw key remains in page memory only.

The dashboard should show only useful customer-safe authoritative information:

- credential state
- CRM/Integration evaluation type
- grant ID and key ID/prefix
- expiry
- quota limit, admitted usage, and remaining quota
- authorized canonical tasks and prepared bindings
- current execution progression: `admitted -> executing -> succeeded/failed -> evidence persisted`
- latest safe execution receipt/evidence
- quota effect for the operation (`+1` newly admitted, `+0` durable replay/status read)
- `production_allowed=false`

The customer dashboard is not an authority surface. It cannot issue/revoke grants, alter quota, alter scope, restore credentials, or declare final qualification.

## Execute a task

Endpoint:

```text
POST /evaluation/runtime/task-execute
```

Example:

```bash
curl -X POST "https://<maestro-host>/evaluation/runtime/task-execute" \
  -H "X-API-Key: $MAESTRO_EVALUATION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "crm.customer_context",
    "binding_id": "evaluation.crm.sandbox",
    "idempotency_key": "customer-test-000001",
    "task_input": {
      "customer_id": "synthetic-customer-001"
    }
  }'
```

The requested task must match the prepared binding and both must be inside the Evaluation Grant authority envelope.

## Idempotency

Use one stable `idempotency_key` per logical operation.

- retry of the same logical request: reuse the same key
- new logical operation: use a new key
- same key with different input: HTTP 409
- a completed replay does not execute the external operation again and does not consume another quota unit
- an unresolved/failed prior network outcome is blocked from automatic replay

## Quota semantics

Evaluation quota is defined as **admitted executions**, not authentication attempts or commercial subscription usage.

- authentication/credential validation: 0 units
- customer status/dashboard refresh: 0 units
- rejected task/binding/configuration request before execution admission: 0 units
- first successful transactional execution claim: 1 unit
- durable replay of that same idempotency key: 0 additional units
- an admitted execution that later fails during the external network operation remains consumed because capacity was admitted and a network outcome may be uncertain

Current fixed Evaluation policy:

- CRM: 100 admitted executions
- Integration: 2 × CRM = 200 admitted executions

The grant type determines the quota. The customer cannot request a larger limit through the dashboard, and the External Evaluation UI must not present a commercial plan or arbitrary quota override as evaluation authority.

When quota is exhausted, a new execution claim returns HTTP 429.

## Key handoff lifecycle

Administrative audit states:

1. `issued`
2. `delivery_confirmed` — administrator confirms the key was sent
3. `acknowledged` — receipt is confirmed
4. `revoked` — possible at any point

Delivery and receipt states are audit evidence only. They do not expand runtime authority. Revocation is authoritative and the key is rejected immediately by runtime verification.

## Customer and Admin reports

A successful evaluation produces two views over the same authoritative execution ledger:

### Customer report

The customer receives a safe receipt for their own Evaluation credential. It may contain grant/key safe identifiers, evaluation type, quota state, task/binding IDs, timestamps, execution status, HTTP/evidence metadata, and evidence hashes. It must not contain the raw API key, raw task input, sandbox/provider credentials, provider responses, internal authority secrets, or an automatic production-readiness verdict.

### Platform Administrator report

The Platform Administrator receives the authoritative audit copy, including the aggregate final summary and safe execution receipts. The final summary uses:

- `report_type=external_evaluation_final_summary`
- `qualification_decision=operator_required`

The system may derive an audit outcome such as complete/needs-review, but only the human operator may make the final qualification/release decision.

## Customer-owned sandbox requirements

Start with a dedicated non-production HTTPS sandbox using synthetic data and read-only operations where possible. Provide:

- public HTTPS sandbox base URL
- endpoint method/path
- JSON request/response contract
- synthetic test identifiers
- authentication type
- dedicated short-lived sandbox credential when authentication is required
- expected success codes
- technical contact

Do not provide production credentials or production data. Private-only/VPN endpoints require a future private connectivity mechanism and must not be exposed through ad-hoc public tunnels.

## Recommended qualification sequence

1. prove the full flow against the project-owned Render sandbox
2. create a CRM or Integration grant and verify the corresponding fixed quota
3. issue the one-time Evaluation API key and safe technical handoff text
4. confirm delivery and receipt acknowledgement
5. connect the customer dashboard and verify grant/type/scope/quota metadata at +0
6. execute one new request and verify one admitted-execution unit is consumed
7. verify dashboard progression and customer safe receipt/evidence
8. replay the same request and verify no additional unit is consumed
9. use the same idempotency key with different input and verify HTTP 409
10. verify the Admin audit copy reflects the same execution
11. revoke the individual key and verify the next request is rejected
12. qualify grant-wide revocation separately and verify active linked keys are revoked
13. verify evidence/report output contains hashes/metadata only and no raw key or raw task input
14. only then qualify a customer-owned sandbox

Production access remains disabled throughout External Evaluation.