# Maestro Agent Identity Carrier — M1-R3

## Status

```text
Phase: M1 — Measurement Foundation
Increment: M1-R3
Mode: Pure carrier contract
Runtime integration: Disabled
Agent execution: Disabled
Measurement emission: Disabled
Shadow Store writes: Disabled
Commercial enforcement: Disabled
Quota approval: False
Invoicing approval: False
Checkout approval: False
Settlement approval: False
```

## Purpose

M1-R3 defines a reference-only carrier that can transport the commercial
execution identity toward a future Agent Runtime boundary.

It does not modify or import `RuntimeAdapter`, does not call `run_agent`, and
does not alter `AgentExecutionResult`.

## Composition

```text
MaestroExecutionAttemptContext
    -> MaestroCommercialExecutionIdentity
        -> MaestroAgentExecutionIdentityCarrier
```

No existing contract is duplicated or replaced.

## Carrier fields

```text
identity
agent_reference
task_reference
requested_at
correlation_reference
```

Only references are allowed. Raw task content, secrets, prompts, responses,
provider payloads, and agent output are prohibited.

## BYOK policy

```text
LLM_CONNECTION_POLICY = byok_only
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
```

M1-R3 does not enable LLM execution or measurement.

## Reference payload

`to_reference_payload()` returns only declared non-sensitive references. It
performs no network access, persistence, dispatch, execution, or measurement
emission.

## Non-goals

M1-R3 does not:

- connect the carrier to an adapter;
- change Agent Runtime signatures;
- execute an agent;
- emit or persist Maestro measurements;
- activate commercial enforcement;
- mutate quota, entitlement, checkout, invoicing, or settlement behavior;
- enable governed LLM measurement.

## Next gate

The next increment may define a no-op carrier-aware adapter protocol or bridge.
Any bridge must remain disconnected from production runtime until separately
approved and tested.
