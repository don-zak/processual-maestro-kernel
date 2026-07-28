# Maestro Shadow Measurement R2

## Status

- Version: `maestro-unit-v1-calibration-r2a`
- Shadow only: yes
- Approved for quota: no
- Approved for invoicing: no
- Approved for checkout: no
- Approved for runtime enforcement: no

## Scope

R2A defines immutable measurement contracts and an isolated,
append-only JSONL store. It does not instrument production execution.

## Safety boundary

The measurement layer must not import or call legacy pricing, quota,
subscription, checkout, invoicing, payment, or runtime middleware.

Measurement storage is best effort. A storage failure must never block
or alter customer execution.

## Data minimization

Measurements contain governed identifiers, UTC timestamps, Decimal
durations and costs, outcome classifications, calibrated quantities,
resource bands, and failure ownership.

Measurements must not contain raw requests, prompts, documents,
responses, credentials, API keys, tokens, headers, cookies, or secrets.

## Idempotency

`measurement_id` is the append idempotency key. Repeated writes with
the same identifier are ignored. `execution_id` and `attempt_id`
remain separate so retries can be studied without double settlement.

## Runtime integration

R2A intentionally has no runtime integration. R2B may add an explicit
instrumentation boundary only after a production execution authority
is identified and proven not to duplicate retries or HTTP requests.
