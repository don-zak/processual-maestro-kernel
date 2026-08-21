# CAMARA QoD R3 — Provider-Neutral Connector Design Candidate

**Date:** 2026-08-19  
**Stage:** R3 preparation  
**Status:** **DESIGN CANDIDATE ONLY — NO CONNECTOR APPROVAL**

## Purpose

Prepare a provider-neutral CAMARA QoD connector design for independent review while preserving current fail-closed authority.

This design deliberately reuses the repository's existing connector binding and secret-reference architecture instead of introducing a parallel endpoint/secret model.

## Existing control-plane primitives to reuse

The repository already provides default-deny connector metadata in:

`processual_api/integrations/connector_bindings.py`

Relevant primitives include:

- `ConnectorTargetReference` — unresolved environment target metadata;
- `ConnectorSecretReference` — unresolved customer-vault reference without secret material;
- `ConnectorEnvironmentBinding` — unapproved connector/target/secret binding;
- required operator inputs;
- explicit `configured=false`;
- explicit `validated=false`;
- explicit `approved=false`;
- explicit `runtime_enabled=false`;
- explicit `external_http_enabled=false`;
- explicit `production_allowed=false`;
- explicit `credentials_resolved=false`.

The CAMARA QoD design must extend these existing boundaries rather than bypass them.

## Design principles

1. Governed CAMARA semantic mapping remains provider-neutral and immutable.
2. Provider adapters bind to governed operation IDs; they do not rewrite the governed contract.
3. Endpoint configuration is by managed reference only; raw endpoint authority is not embedded in semantic mapping.
4. Credentials are resolved by managed secret reference only; raw secret values are never persisted in connector configuration or UI projection.
5. Provider capability limitations are explicit and fail closed.
6. Runtime admission requires all existing entitlement, quota and write-approval checks plus provider sandbox proof and independent connector approval.
7. External mock evidence cannot activate runtime authority.
8. Staging and production remain separately authorized environments.

## Required connector contract

A future executable CAMARA QoD connector candidate should declare at least:

- `connector_id`;
- provider identifier;
- provider API version;
- supported governed operation IDs;
- unsupported governed operation IDs;
- supported environments;
- authentication profile ID;
- target reference ID;
- secret reference IDs;
- endpoint path bindings;
- timeout policy;
- retry policy;
- idempotency policy;
- error normalization policy;
- entitlement requirement per operation;
- quota meter per operation;
- write approval requirement per mutating operation;
- audit projection policy;
- PII redaction policy;
- telemetry fields;
- kill-switch contract;
- rollback/disable behavior.

## Capability matrix contract

Every provider adapter must expose an explicit capability matrix against the five governed CAMARA operations:

| Governed operation | Provider binding | Capability state |
| --- | --- | --- |
| `createSession` | provider-specific | `supported` / `unsupported` / `unproven` |
| `getSession` | provider-specific | `supported` / `unsupported` / `unproven` |
| `deleteSession` | provider-specific | `supported` / `unsupported` / `unproven` |
| `extendQosSessionDuration` | provider-specific | `supported` / `unsupported` / `unproven` |
| `retrieveSessionsByDevice` | provider-specific | `supported` / `unsupported` / `unproven` |

No adapter may silently omit a governed operation.

If an operation is `unsupported` or `unproven`, runtime dispatch for that operation must fail before external HTTP execution.

## Authentication lifecycle

For CIBA-capable providers, the connector design must specify:

1. managed client credential lookup;
2. authorization request creation;
3. `auth_req_id` held in memory only;
4. token exchange;
5. access token held in memory only;
6. expiry handling;
7. token renewal/re-authentication policy;
8. revocation behavior;
9. credential rotation behavior;
10. zero raw token/secret persistence in evidence or logs.

Authentication success alone grants no provider or runtime authority.

## Endpoint and secret references

Use the existing `ConnectorTargetReference` and `ConnectorSecretReference` model.

A CAMARA QoD provider candidate must not introduce:

- literal provider credentials in source;
- raw secret values in environment binding records;
- raw secret values in browser payloads;
- automatic endpoint activation;
- automatic credential resolution from mock evidence.

Managed secret reference completion remains a prerequisite for reusable connector execution.

## Timeout and retry policy

The connector contract must define separate timeout values for:

- authorization request;
- token exchange;
- create/get/delete/extend/retrieve requests.

Retries must be operation-aware:

- do not blindly retry mutating operations;
- require explicit idempotency semantics before retrying create/extend/delete;
- bounded retry count only;
- no unbounded exponential retry loop;
- retry decisions must be auditable.

## Idempotency policy

For every mutating operation, define whether the provider supports an idempotency key or another deterministic replay boundary.

If idempotency cannot be proven, ambiguous network failures after request transmission must not be automatically replayed.

## Error normalization

Provider responses must be normalized into a provider-neutral error envelope without altering observed semantics.

The normalization layer must preserve:

- upstream HTTP status;
- provider error class/code when safe;
- normalized internal category;
- retryability decision;
- correlation/audit reference;
- redacted diagnostic metadata.

It must not convert known divergence into conformance.

Example: a provider returning HTTP 200 for a never-created session must not be relabeled as a conformant CAMARA missing-resource response.

## Admission controls

Before any external QoD operation dispatch, runtime must require:

- exact task registration;
- exact entitlement;
- positive quota evidence;
- write approval for create/delete/extend;
- provider/environment binding configured and validated;
- managed credentials resolved;
- governed provider sandbox proof required by policy;
- `runtime_connector_approved=true`;
- environment-specific authorization;
- kill switch not engaged.

Any failed or unknown check denies execution.

## Audit and privacy

Audit projection should record only what is necessary to reconstruct the decision and external interaction safely.

Allowed examples:

- connector ID;
- provider/version;
- governed operation ID;
- target reference ID;
- secret reference ID (reference only, not value);
- approval reference;
- quota meter result;
- upstream status;
- normalized error category;
- latency;
- request/response hashes where appropriate and privacy-reviewed.

Disallowed by default:

- OAuth access tokens;
- client secrets;
- `auth_req_id` values;
- raw phone numbers/device identifiers unless explicitly required and approved;
- raw session IDs in broad logs;
- raw request/response bodies containing PII.

## Kill switch and rollback

A provider connector candidate must support immediate disablement without modifying the governed semantic blob.

Disablement must be possible at the provider/environment binding or connector authority layer.

Rollback must restore a known fail-closed state:

- connector runtime disabled;
- external HTTP disabled;
- credentials unresolved/unavailable to runtime;
- production authority false.

## Telefonica application of this design

Under the current R2 recommendation, Telefonica v0.10 remains evidence-only.

Therefore this R3 candidate must **not** instantiate or approve an executable Telefonica adapter now.

If governance later chooses a reduced-capability adapter, it must explicitly encode:

- `retrieveSessionsByDevice = unsupported`;
- missing-session divergence policy;
- provider API version `v0.10`;
- four-operation external mock evidence scope;
- operator-network proof state separately;
- independent connector approval state separately.

## Review checklist

R3 independent review should verify:

- no duplicate connector-binding architecture was introduced;
- semantic mapping remains provider-neutral;
- provider capability matrix is explicit;
- unsupported operations fail before network I/O;
- managed endpoint/secret references are used;
- CIBA/token lifecycle is memory-only for sensitive values;
- timeout/retry/idempotency behavior is explicit;
- entitlement/quota/write approvals are enforced;
- error normalization preserves divergence evidence;
- audit/redaction policy is sufficient;
- kill switch and rollback are testable;
- provider/runtime/staging/production authority remains fail closed until separately approved.

## Current authority

This design candidate does not change:

- `operator_network_qos_proven=false`;
- `provider_sandbox_proven=false`;
- `runtime_connector_approved=false`;
- `staging_allowed=false`;
- `production_allowed=false`.

Maximum outcome of R3 in the current program remains **sandbox connector candidate approval**, not production approval.