# CAMARA QoD R2 — Provider Compatibility Governance Review

**Date:** 2026-08-19  
**Review stage:** R2 — Provider Compatibility Governance Review  
**Review status:** **RECOMMENDATION READY — GOVERNANCE DECISION REQUIRED**

## Purpose

This review converts the retained Telefonica QoD v0.10 interoperability evidence into an explicit provider-compatibility recommendation without changing the governed CAMARA QoD v1.1.0 contract and without granting connector authority.

## Governed contract remains immutable

The governed CAMARA QoD v1.1.0 outbound contract remains exactly five operations:

1. `createSession`
2. `getSession`
3. `deleteSession`
4. `extendQosSessionDuration`
5. `retrieveSessionsByDevice`

`postNotification` remains excluded from outbound binding.

No provider-specific limitation in this review modifies or silently waives that governed contract.

## Reviewed provider evidence

Telefonica Open Gateway QoD v0.10 has retained external sandbox/mock interoperability evidence for four governed operation shapes:

- `createSession` — positive-path proof retained;
- `getSession` — positive-path proof retained for a created session;
- `deleteSession` — positive-path proof retained;
- `extendQosSessionDuration` — positive-path proof retained.

The current reviewed Telefonica QoD v0.10 surface does not expose or externally prove:

- `retrieveSessionsByDevice` / `POST /retrieve-sessions`.

The provider surface also has a retained negative-path divergence:

- a fresh, never-created session identifier returned HTTP 200 from `getSession`;
- the reviewed provider documentation specifies HTTP 404 for session-not-found.

Therefore the current provider compatibility state remains:

`partial_interoperability_with_negative_path_divergence`.

## Options considered

### Option A — Require exact/full provider conformance before connector work

Require a provider/version surface that proves all five governed CAMARA QoD v1.1.0 operations and the required failure semantics before any provider-specific connector candidate is advanced.

**Advantages**

- simplest conformance model;
- no reduced-capability policy required;
- lowest semantic ambiguity at runtime.

**Disadvantages**

- blocks Telefonica v0.10 connector work despite useful four-operation interoperability evidence;
- depends on availability of a provider/version that may not currently expose the fifth operation.

### Option B — Approve a reduced-capability Telefonica adapter profile

Create a provider-specific adapter profile that explicitly exposes only the operations proven and authorized for Telefonica, while the governed CAMARA contract remains unchanged separately.

**Advantages**

- preserves useful provider interoperability;
- makes missing capability explicit rather than implicit;
- allows provider-specific normalization and error handling.

**Required safeguards**

- explicit capability matrix;
- hard failure for unsupported `retrieveSessionsByDevice`;
- no fallback that fabricates or emulates the missing operation unless separately designed and approved;
- explicit handling of missing-session HTTP 200 divergence;
- provider/version pinning;
- independent runtime connector review;
- operator-network proof remains separately required if provider qualification is desired.

### Option C — Keep Telefonica v0.10 evidence-only

Retain the current Telefonica v0.10 result solely as external interoperability evidence and do not construct a runtime adapter candidate from it.

**Advantages**

- lowest authority risk;
- preserves evidence value without accepting provider-specific semantic debt;
- avoids confusing mock success with operator-network qualification.

**Disadvantages**

- no near-term Telefonica connector candidate;
- requires another provider/version or future Telefonica surface to proceed to runtime connector design.

## R2 recommendation

**Recommended disposition: Option C now — Telefonica v0.10 remains evidence-only.**

Option B may be reconsidered later only through a separate explicit governance decision after the following are available:

1. a complete provider-specific capability matrix;
2. a formal unsupported-operation policy for `retrieveSessionsByDevice`;
3. an explicit missing-session divergence normalization policy that does not label HTTP 200 as conformance;
4. managed endpoint and secret-reference design;
5. timeout, retry, idempotency, quota, entitlement, write-approval, audit and redaction controls;
6. independent connector design/security review.

## Rationale

The current evidence is strong enough to demonstrate useful four-operation external mock interoperability, but it is not strong enough to justify runtime connector authority because two compatibility boundaries remain material:

- one of the five governed operations is absent/unproven;
- documented negative-path semantics diverge from observed mock behavior.

Keeping Telefonica v0.10 evidence-only preserves the interoperability result without weakening the governed CAMARA contract or introducing implicit waivers.

## Operator-network qualification remains separate

This R2 recommendation does not satisfy S2.

The project still requires a non-mock/operator-backed environment to prove actual operator-network QoS behavior. External Telefonica sandbox/mock interoperability cannot set:

- `operator_network_qos_proven=true`;
- `provider_sandbox_proven=true` for the governed CAMARA contract.

## Authority state after this review

This document is a review recommendation, not an authorization decision. The following remain unchanged:

- `operator_network_qos_proven=false`;
- `governed_camara_v1_1_provider_sandbox_proven=false`;
- `provider_sandbox_proven=false`;
- `runtime_connector_approved=false`;
- `staging_allowed=false`;
- `production_allowed=false`.

## Required governance action

An authorized governance actor must explicitly record one of:

- **A — require full provider conformance**;
- **B — approve reduced-capability adapter profile with stated conditions**;
- **C — retain Telefonica v0.10 as evidence-only**.

Until that decision exists, provider connector work remains fail-closed.

## Recommended next engineering action

Proceed with work that does not depend on provider connector authority:

1. resolve or accept R1-C1 provenance clarification;
2. obtain a non-mock/operator-backed QoD test environment for S2;
3. prepare a provider-neutral managed endpoint/secret connector contract for later R3 review;
4. do not set `runtime_connector_approved=true`.