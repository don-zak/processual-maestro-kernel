# EXTERNAL-CONNECTIVITY-16C — Governed Connector Operation Plans

EXTERNAL-CONNECTIVITY-16C adds a Control Plane planning layer above the disabled
16A connector capability contracts and the unresolved 16B environment bindings.
It does not execute a connector operation.

## Contract inventory

The immutable registry contains:

- 101 operation plans;
- 101 approval requirements;
- 101 audit projections;
- 404 planning steps.

Read capabilities receive sandbox and production planning references. Write and
restricted capabilities remain sandbox-only because their 16A capability
contracts are sandbox-only.

## Required operation metadata

Every plan requires an operation identifier, tenant binding, payload hash,
idempotency key, and expiry metadata. These fields are schema requirements only;
16C does not accept, persist, hash, or transmit a customer payload.

Approval-required capabilities preserve supervisor-session review, requester and approver separation,
approval expiry before any future execution, and approval
invalidation when a payload hash changes. Approval status remains
`not_requested`, and no approval is satisfied by this phase.

## Safe step sequence

Each plan declares four non-executable steps:

1. validate operation metadata;
2. validate the unresolved 16B binding reference;
3. project the future audit event schema;
4. block dispatch.

The final step is intentionally `block_dispatch`. There is no dispatcher, HTTP
client, credential resolver, retry worker, timeout worker, rollback worker, or
background synchronization process.

## Audit projection

The audit projection describes required future fields such as operation ID,
plan ID, connector ID, binding ID, capability ID, scope, environment, tenant ID,
payload hash, idempotency key, requester actor, approver actor, approval status,
creation time, and expiry time. It does not persist or emit an audit event and
does not enable an external audit sink.

## Default-deny posture

Every plan preserves:

```text
action_execution_allowed = false
runtime_enabled = false
external_http_enabled = false
production_allowed = false
automatic_activation_allowed = false
credentials_resolution_allowed = false
```

Every step also preserves execution, external HTTP, and credential-resolution
flags as false. Approval requirements remain unsatisfied. Audit projections
remain unpersisted and un-emitted.

## Explicit exclusions

16C adds no customer endpoint, no secret value, no API token, no OAuth exchange,
no certificate material, no external HTTP, no runtime dispatch, no production
approval, no direct database integration, and no customer-specific operation
payload.

A later phase may add a disabled mock dispatcher for local contract proof, but it
must remain separate from these planning contracts and must not silently convert
any 16C plan into executable behavior.
