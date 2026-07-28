# Maestro Execution Authority Gap R2B

## Decision

The repository does not yet expose one unified production execution
authority suitable for Maestro shadow measurement instrumentation.

CAL-R2B therefore defines only a future observation boundary. Runtime
instrumentation remains disabled.

## Authorities discovered

The repository contains multiple independent execution families:

- provider-specific LLM adapters;
- direct provider HTTP calls in the LLM report generator;
- adaptive kernel runtime commands;
- authentication delivery dispatch and workers;
- connector contracts and synthetic sandbox workflows;
- an abstract agent runtime contract without a proven unified
  production call path.

These paths do not currently share one governed execution identifier,
attempt identifier, retry boundary, completion contract, or
idempotency boundary.

## Unsafe integration points

HTTP middleware is not an execution authority. It observes requests,
not provider attempts, retries, partial completion, or final outcomes.

Provider adapters alone are also insufficient because some provider
calls bypass them and other execution families do not use them.

Synthetic, training, fake-sandbox, and unapproved connector paths must
not be treated as customer production execution.

## Required prerequisites

Before shadow measurement integration, the runtime must provide:

1. one stable execution identifier across all retries;
2. a unique attempt identifier for each actual attempt;
3. a stable idempotency key;
4. explicit start and completion events;
5. completed, partially completed, failed, cancelled, duplicate, and
   review-required outcomes;
6. provider or connector usage returned as structured metadata;
7. failure ownership classification;
8. a best-effort observer that cannot affect customer execution;
9. no coupling to quota, checkout, invoicing, or settlement.

## Current status

- Discovery complete.
- Unified authority absent.
- Runtime instrumentation disabled.
- Shadow measurement persistence remains isolated.
- Commercial enforcement remains prohibited.

A later runtime-foundation phase must establish the unified authority
before CAL measurement integration can proceed.

## LLM and BYOK boundary

All production customer LLM connections must use credentials owned by the
customer or institution through the BYOK model.

The platform must not provide or silently fall back to a platform-owned LLM
credential for customer execution. A missing, invalid, revoked, or unauthorized
customer credential must prevent the live provider call rather than trigger a
platform-key fallback.

Execution-authority and calibration contracts may carry only safe references,
such as provider identifiers, credential-profile identifiers, secret-reference
identifiers, and tenant identifiers. They must never carry raw API keys,
authorization headers, bearer tokens, passwords, cookies, prompts, responses,
or other raw provider payloads.

Credential ownership checks and secret resolution belong to a separate
credential authority. Secret resolution must occur outside the calibration
module and only at the last execution boundary where the provider client
requires the credential.

Estimated provider cost remains shadow-only analytical metadata. It does not
mean that the platform paid the provider cost, and it must not create quota,
invoice, checkout, payment, subscription, pricing, or settlement effects.

CAL-R2B remains discovery-only. It does not resolve credentials, initialize
provider clients, execute live LLM calls, emit runtime measurements, or connect
the observer to production execution.
