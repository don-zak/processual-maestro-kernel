# External Evaluation Client Guide

This guide is the customer-facing operating contract for non-production Maestro External Evaluation.

## What the customer receives

The customer receives a Maestro Evaluation API key separately from the non-secret access package. The raw key is displayed only once at issue time and must be stored in a secret manager or environment variable. The customer does not receive Render credentials, database credentials, administrator access, or production credentials.

The non-secret package should include:

- Maestro Evaluation base URL
- Evaluation Grant ID and Key ID/prefix
- evaluation type (`crm` or `integration`)
- quota and expiry
- allowed task IDs
- allowed binding IDs
- allowed API endpoints
- example request and expected response/evidence fields
- support contact

## Customer data required to issue a key

No customer secret, password, production API key, billing information, or production dataset is required to generate the Maestro key. The administrator needs only identification and scope metadata such as `client_id`, `issued_to`, purpose, duration, tasks, endpoints, and prepared sandbox bindings.

If Maestro must call a customer-owned sandbox, its credential is a separate short-lived sandbox credential. The binding stores only a secret reference. Raw authentication headers must never be embedded in endpoint-binding settings.

## Authentication

Send the key in the `X-API-Key` header:

```bash
export MAESTRO_EVALUATION_API_KEY='pmk_...'
```

Never commit the key to source control, tickets, logs, screenshots, or client-side browser code.

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
      "customer_id": "demo-customer-001"
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

Evaluation quota is defined as **admitted executions**, not authentication attempts.

- authentication/credential validation: 0 units
- rejected task/binding/configuration request before execution admission: 0 units
- first successful transactional execution claim: 1 unit
- durable replay of that same idempotency key: 0 additional units
- an admitted execution that later fails during the external network operation remains consumed because capacity was admitted and a network outcome may be uncertain

Current policy:

- CRM: 100 units
- Integration: 2 × CRM = 200 units

When quota is exhausted, a new execution claim returns HTTP 429.

## Key handoff lifecycle

Administrative audit states:

1. `issued`
2. `delivery_confirmed` — administrator confirms the key was sent
3. `acknowledged` — receipt is confirmed
4. `revoked` — possible at any point

Delivery and receipt states are audit evidence only. They do not expand runtime authority. Revocation is authoritative and the key is rejected immediately by runtime verification.

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
2. issue a bounded Integration key
3. execute one new request and verify one unit is consumed
4. replay the same request and verify no additional unit is consumed
5. use the same idempotency key with different input and verify HTTP 409
6. revoke the key and verify the next request is rejected
7. verify evidence contains hashes/metadata only and no raw key or raw task input
8. only then qualify a customer-owned sandbox

Production access remains disabled throughout External Evaluation.
