# AUTH-R6B delivery dispatcher

AUTH-R6B turns the encrypted authentication delivery outbox into a bounded,
restart-safe worker. Registration and resend still commit user, action-token,
and encrypted outbox state without making an external provider call.

The worker claims due rows in PostgreSQL with `FOR UPDATE SKIP LOCKED`, writes a
unique `claim_id`, records the lease timestamp, and increments the attempt count
before committing. Provider I/O happens only after that claim transaction has
closed. Success and failure finalization require the same `claim_id`, preventing
a worker whose lease expired from overwriting a newer worker's result.

Every provider request uses the stable idempotency key
`pmk-auth-delivery-v1:<outbox-id>`. A crash after provider acceptance and before
database finalization therefore retries with the same key. Transient failures
use capped exponential backoff with deterministic jitter. Terminally ineligible
tokens and attempts reaching the configured maximum move to explicit
dead-letter state.

The provider endpoint and public authentication base URL must be clean HTTPS
URLs configured by deployment authority. They are never derived from an HTTP
Host header. Provider credentials, delivery encryption keys, and old key-ring
versions remain in the secret manager. The worker emits only aggregate counts
and sanitized error codes; it does not log recipient addresses, raw tokens,
verification URLs, ciphertext, provider response bodies, or authorization
headers.

Run one bounded batch with:

```text
python -m processual_api.auth.delivery_worker --once
```

Continuous scheduling, alert routing, provider-domain configuration, and
dead-letter operations are deployment responsibilities built around this
bounded command.
