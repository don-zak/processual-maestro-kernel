# Maestro Commercial Execution Identity — M1-R2

## Status

```text
Phase: M1 — Measurement Foundation
Increment: M1-R2
Mode: Pure contract
Runtime integration: Disabled
Measurement emission: Disabled
Shadow Store writes: Disabled
Commercial enforcement: Disabled
Quota approval: False
Invoicing approval: False
Checkout approval: False
Settlement approval: False
```

## Decision

M1-R2 does not modify `MaestroExecutionAttemptContext`. It composes the
existing authority context inside `MaestroCommercialExecutionIdentity`.

This preserves the established execution-authority contract and avoids
breaking existing calibration, readiness, shadow-measurement, or delivery
reference tests.

## Initial execution family

M1-R2 supports only:

```text
MaestroExecutionAuthorityKind.AGENT_RUNTIME
```

Governed LLM execution remains outside this increment because its execution
ownership, attempt identity, structured usage, tenant binding, and credential
profile binding are not yet unified.

## Required identity

The composed identity exposes:

```text
execution_id
attempt_id
authority_kind
started_at
retry_ordinal
idempotency_key
parent_execution_id
tenant_reference
credential_profile_reference
workload_family_id
credential_ownership
```

An idempotency key is mandatory even for the first commercial attempt.

## Credential policy

```text
LLM_CONNECTION_POLICY = byok_only
credential_ownership = customer_byok
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False
```

Only credential-profile references are allowed.

## Non-goals

M1-R2 does not change runtime interfaces, call `run_agent`, connect an
observer, emit measurements, write to the Shadow Store, mutate quotas or
entitlements, or activate checkout, invoicing, payment, or settlement.

## Next gate

A later increment may define a no-op adapter-side carrier contract for this
identity. Runtime integration remains separately gated.
