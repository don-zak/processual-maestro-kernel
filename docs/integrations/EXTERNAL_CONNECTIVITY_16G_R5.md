# EXTERNAL-CONNECTIVITY-16G-R5 — Outbound allowlist and TLS approval simulation

## Purpose and boundary

16G-R5 is an isolated, reference-only training simulation. It projects the
accepted 16G-R2 outbound and TLS references into the existing 16F-R3A
readiness assessment after validating an existing pilot Activation Permission
Key.

It does not apply an allowlist, authorize egress, create a TLS context, or
open any network connection.

## Reused contracts

R5 reuses:

- `TrainingCustomerInputSubmission`;
- the canonical `TrainingCustomerInputReview`;
- `TrainingActivationIsolation`;
- `OutboundAllowlistTlsReferenceSubmission`;
- `assess_outbound_allowlist_tls_readiness`;
- the existing task create, key issue, key validation, and revoke services.

Supported minimum TLS reference selections are `tls_1_2` and `tls_1_3`.
They are policy references only and do not instantiate TLS.

## Canonical input gate

The supplied R2 submission is reviewed again. The supplied review must equal
that canonical immutable result and must be
`ready_for_supervisor_review`. Missing, excessive, unsafe, mismatched, or
forged input is rejected before any isolated store or audit file is created.

R5 maps eleven outbound references:

- allowlist;
- host;
- DNS policy;
- port policy;
- CA policy;
- certificate-pinning policy;
- proxy policy;
- egress authorization;
- security review;
- operator approval;
- kill switch.

## Training lifecycle

The sequence is:

1. Validate the canonical R2 review.
2. Create an isolated training task.
3. Issue one Activation Permission Key.
4. Validate that key against persisted state.
5. Construct the existing eleven-field outbound/TLS submission.
6. Run the existing readiness assessment.
7. Produce synthetic, non-persisted approval metadata.
8. Revoke the task and key.
9. Restore caller environment paths in `finally`.

Failure after task creation causes a revocation attempt in `finally`.

`network_policy_references_received_for_review` means review readiness only.
It is not network authorization.

## Default-deny outcome

Every result preserves:

- `allowlist_applied=false`
- `dns_resolution_performed=false`
- `port_opened=false`
- `tls_context_created=false`
- `ca_bundle_loaded=false`
- `certificate_loaded=false`
- `certificate_pin_applied=false`
- `proxy_configured=false`
- `egress_authorized=false`
- `kill_switch_armed=false`
- `connection_attempted=false`
- `external_http_enabled=false`
- `socket_access_enabled=false`
- `persistence_allowed=false`
- `background_task_allowed=false`
- `route_exposure_allowed=false`
- `runtime_enabled=false`
- `production_allowed=false`
- `automatic_activation_allowed=false`

There is no DNS resolution, no port opening, no socket, no TLS context, no
certificate or CA loading, no proxy configuration, no executable egress
authorization, no external HTTP, no sandbox launch, and no production
activation.

## Persistence and revocation

The raw Activation Permission Key and all outbound references are absent from
the returned model, isolated task store, and isolated audit. Only the existing
safe pilot task and audit events are persisted.

A successful or aborted simulation ends with the task and key revoked.

## Next phase

16G-R6 may invoke the existing deterministic local fake sandbox transport
using synthetic metadata only. It must remain read-only, prohibit external
HTTP, avoid parallel transport implementations, and require all earlier
training gates.
