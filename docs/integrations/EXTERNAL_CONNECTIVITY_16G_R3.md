# EXTERNAL-CONNECTIVITY-16G-R3 — Governed one-time activation training lifecycle

## Status and purpose

16G-R3 is an isolated training exercise over the existing
`integration_pilot_controls` service. It proves creation, one-time Activation
Permission Key issuance, suspension, resumption, and revocation without
granting connectivity or production authority.

It is not R2B or R3B real connectivity. It does not activate a real operator
sandbox and does not convert customer references into credentials.

## Entry gate

The lifecycle accepts only an immutable 16G-R2
`TrainingCustomerInputReview` whose status is
`ready_for_supervisor_review`. Incomplete, excessive, or unsafe customer input
is rejected before any training task or audit file is created.

The training exercise requires explicit isolated store and isolated audit file
paths. The default pilot task store and default administrative audit path are
prohibited.

## Exercised lifecycle

The governed sequence is:

1. Create an isolated training task.
2. Issue one Activation Permission Key.
3. Expose the raw key only in the successful issuance response.
4. Attempt a second issuance and require
   `activation_permission_key_already_issued`.
5. Prove `second_issuance_rejected=True`.
6. Prove the rejected attempt changes neither store, timeline, nor audit.
7. Suspend the task and prove issuance is unavailable.
8. Resume the task and prove prior issuance still blocks reissuance.
9. Revoke the task and leave its key marked revoked.
10. Restore the caller's environment paths in `finally`.

The service rejects reissuance if any persisted issuance marker exists:

- `activation_permission_key_id`
- `activation_permission_key_hash`
- `activation_permission_issued_at`
- status `activation_permission_issued`

A forged request payload cannot erase these persisted markers.

## Raw-key boundary

The first successful response contains the raw key once. The raw key is absent
from:

- public task listing;
- the isolated store;
- the isolated audit;
- the returned `TrainingActivationExercise`.

The stored hash is removed from public task representations. A rejected
issuance returns neither a new raw key nor the previous raw key, creates no
second issuance timeline event, and creates no second issuance audit event.

## Isolation and non-authority

16G-R3 preserves all default-deny boundaries:

- `external_http_enabled=false`
- `runtime_enabled=false`
- `production_allowed=false`
- sandbox grant disabled
- runtime connector grant disabled
- no secret resolution
- no credentials retrieval
- no external HTTP
- no DNS resolution
- no socket
- no TLS context
- no connector dispatcher
- no fake transport invocation
- no sandbox launch
- no production activation

Only synthetic training identifiers and safe references are used.

## Regression requirements

The direct regression suite proves:

- each persisted issuance marker independently prevents issuance;
- the second issuance is side-effect free;
- suspend blocks issuance;
- resume does not restore issuance authority;
- the lifecycle ends in `revoked`;
- only one issuance event exists in timeline and audit;
- raw-key leakage does not occur;
- environment overrides are restored;
- shared/default paths are rejected;
- network and secret SDK imports are absent;
- the public package exports the 16G-R3 surface.

## Next phase

16G-R4 may simulate a disabled secret-provider binding using references only.
It must not resolve a secret, import a provider SDK for execution, or loosen
any runtime, network, sandbox, or production guardrail.
