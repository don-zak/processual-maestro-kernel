# Maestro Agent Identity Bridge — M1-R4

## Status

```text
Phase: M1 — Measurement Foundation
Increment: M1-R4
Mode: No-op bridge contract
Runtime integration: Disabled
Agent execution: Disabled
Bridge dispatch: Disabled
Measurement emission: Disabled
Shadow Store writes: Disabled
Commercial enforcement: Disabled
Quota approval: False
Invoicing approval: False
Checkout approval: False
Settlement approval: False
```

## Purpose

M1-R4 defines a pure bridge protocol between the M1-R3 identity carrier and a
future Agent Runtime integration boundary.

The default implementation is `NoOpMaestroAgentIdentityBridge`. It accepts a
validated carrier and returns a deterministic disconnected receipt.

## Composition

```text
MaestroExecutionAttemptContext
    -> MaestroCommercialExecutionIdentity
        -> MaestroAgentExecutionIdentityCarrier
            -> NoOpMaestroAgentIdentityBridge
```

## Receipt behavior

The receipt always records:

```text
outcome = noop_disconnected
accepted_for_execution = False
measurement_emitted = False
persisted = False
```

Any attempt to construct a receipt with one of those flags enabled fails
closed.

## Runtime boundary

M1-R4 does not import `RuntimeAdapter` or `AgentExecutionResult`, and does not
call `run_agent`.

Mentioning those names in documentation does not constitute integration; AST
boundary tests verify actual imports and calls.

## BYOK and sensitive data

```text
LLM_CONNECTION_POLICY = byok_only
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_TASK_CONTENT_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False
RAW_AGENT_OUTPUT_ALLOWED = False
```

The bridge receives only the already validated reference carrier.

## Non-goals

M1-R4 does not:

- execute or dispatch an agent;
- connect to Agent Runtime;
- emit or persist Maestro measurements;
- activate commercial enforcement;
- mutate quota or entitlement state;
- activate checkout, invoicing, payment, or settlement;
- enable governed LLM execution or measurement.

## Next gate

The next increment may define readiness evidence for a future bridge
integration. Runtime connection remains prohibited until a separate approval
gate is satisfied.
