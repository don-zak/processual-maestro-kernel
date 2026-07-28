# Maestro Execution Authority Readiness R2C

## Decision

CAL-R2C is a discovery and readiness-classification phase.

It does not connect Maestro calibration observers to production execution.
It does not emit, store, price, bill, invoice, settle, or enforce measured
execution.

## Baseline

CAL-R2B established that the repository does not currently expose one unified
production execution authority.

The repository contains multiple execution families that do not yet share one
governed execution identity, attempt identity, retry boundary, completion
contract, or idempotency boundary.

## Objective

CAL-R2C defines a conservative readiness matrix for execution families that
may later participate in a unified execution authority.

A family remains not ready unless every required capability is supported by
explicit runtime evidence.

## Required readiness capabilities

Each candidate execution family must be evaluated for:

1. stable execution identifier;
2. unique attempt identifier;
3. retry ordinal;
4. stable idempotency key;
5. explicit attempt-start event;
6. explicit attempt-completion event;
7. completed, partially completed, failed, cancelled, duplicate, and
   review-required outcomes;
8. structured provider or connector usage metadata;
9. failure ownership classification;
10. best-effort observation that cannot affect customer execution;
11. production-versus-synthetic execution classification;
12. tenant and credential-profile references without secret material.

## LLM and BYOK requirements

All production LLM execution must use customer- or institution-owned
credentials through BYOK.

Platform-owned LLM credentials and implicit fallback credentials are
prohibited.

A missing, invalid, revoked, or unauthorized BYOK credential must prevent the
provider call.

Readiness evidence must never contain raw API keys, authorization headers,
bearer tokens, passwords, cookies, prompts, responses, or raw provider
payloads.

## Commercial isolation

Execution-authority readiness evidence is non-commercial metadata.

It is not approved for:

- quota enforcement;
- plan entitlement changes;
- pricing decisions;
- checkout;
- invoicing;
- payment collection;
- subscription mutation;
- settlement.

Estimated provider cost, when available in a future phase, remains shadow-only
analytical metadata.

## Conservative classification rule

A candidate is ready only when all mandatory capabilities are explicitly
supported.

Unknown, absent, inferred, synthetic-only, or partially implemented
capabilities must classify the candidate as not ready.

## Runtime boundary

CAL-R2C must not:

- import provider clients;
- resolve credentials;
- make network calls;
- initialize runtime adapters;
- invoke connectors;
- emit measurements;
- access measurement persistence;
- mutate commercial state.

## Exit criteria

CAL-R2C is complete when:

1. the readiness contract is immutable and validated;
2. unknown capabilities fail closed;
3. BYOK requirements are explicit;
4. raw credentials and payloads are structurally excluded;
5. runtime and commercial coupling tests pass;
6. no candidate is automatically classified as ready;
7. the full repository test suite passes.