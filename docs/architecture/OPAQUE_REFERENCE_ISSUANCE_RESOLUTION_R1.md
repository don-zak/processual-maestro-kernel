# Opaque Reference Issuance and Resolution — R1

**Status:** DESIGN ONLY — NO RUNTIME AUTHORITY  
**Date:** 2026-08-19

## Purpose

Define the next public/private trust-boundary step required before legacy browser/client surfaces can migrate to `POST /cgt/govern/evaluate`.

The canonical evaluation boundary already accepts only four bounded public fields:

- `formation_ref`
- `evidence_ref`
- `context_ref`
- `evaluated_at`

and returns exactly six sanitized decision fields:

- `existence_rank`
- `dominant_constraint`
- `next_gate`
- `confidence_band`
- `explanation_code`
- `policy_version`

This record does **not** authorize a private runtime connector or define proprietary mathematical inputs. It prevents an unsafe client migration that would invent references which the private trust domain cannot resolve.

## Non-negotiable trust boundary

1. Public code may issue, carry, persist, audit, and revoke only opaque identifiers and public/governance metadata that are independently safe to expose.
2. Public code must not derive a reference by hashing, encoding, serializing, or otherwise transforming proprietary mathematical inputs, raw score vectors, weights, thresholds, calibration values, or private intermediate state.
3. A reference is valid only if there is a reviewed resolution path available inside the private trust domain.
4. Private resolution must terminate inside the private trust domain and must not return resolved private objects to public code.
5. Evaluation results crossing back to public remain limited to the six-field sanitized contract.
6. Resolution failures must collapse to generic boundary errors and must not expose existence tests, storage keys, private object names, provider details, or internal exception text.
7. No public log, trace, browser payload, API response, retained evidence artifact, or audit record may contain resolved private mathematical contents.
8. Public operation remains fail-closed when the private runtime or resolver is unavailable.

## Roles

### Public reference issuer

A future public issuer may create an opaque reference only after it has a legitimate public/governance object to reference and a registered resolution contract. The issuer owns:

- reference syntax/versioning;
- public authorization and quota checks;
- namespace and tenant scoping where applicable;
- expiry/revocation metadata where required;
- audit of issuance/use without recording private contents.

The issuer does not own private mathematical interpretation.

### Private reference resolver

The private runtime already defines the shape required by `PrivateReferenceResolver`:

- `resolve_formation(reference)`
- `resolve_evidence(reference)`
- `resolve_context(reference)`

A concrete resolver must be implemented only after the backing topology is selected and reviewed. It owns private lookup, integrity validation, private authorization checks required by that topology, and conversion to the private objects consumed by `PrivateCGTEvaluationProvider`.

### Public evaluation boundary

The existing public boundary remains the only approved invocation shape. It validates bounded tokens, invokes an explicitly injected provider, validates the exact six-field result, and redacts provider failures.

## Reference properties

A production-capable reference scheme must satisfy all of the following before implementation is accepted:

- opaque: the token does not reveal private values or mathematical semantics;
- bounded: it satisfies the public boundary length/character contract;
- non-authoritative by possession: knowing a token alone must not grant cross-tenant or cross-user access;
- type-bound: formation/evidence/context references cannot be silently substituted for one another;
- environment-bound where applicable: staging/test references cannot resolve against production stores;
- revocable or expirable when the backing object lifecycle requires it;
- auditable without logging resolved private contents;
- collision-safe within the selected namespace;
- resolvable by an explicitly approved private-side mechanism.

## Forbidden shortcuts

The following are architectural violations:

- hashing the browser answer or raw score payload and treating the hash as a resolvable reference without a registered backing record;
- embedding raw answer text, score vectors, weights, thresholds, calibration, private IDs, or serialized private objects in a token;
- letting public code import a private resolver or private mathematical module;
- allowing the private provider to return resolved objects or diagnostic internals to public code;
- using a shared filesystem path or repository path as the public reference contract;
- copying private records into public persistence merely to make resolution convenient;
- silently falling back to public/local mathematical execution when resolution fails.

## Topology proposal now under review

`docs/architecture/OPAQUE_REFERENCE_TOPOLOGY_DECISION_R1.md` records the current **proposed, review-required, non-authoritative** topology:

1. durable PostgreSQL persistence for shared-safe reference metadata only;
2. a dedicated public issuer that generates bounded cryptographically random opaque tokens and enforces tenant/type/environment/lifecycle rules;
3. controlled private resolution through a broker/service boundary implementing the private resolver protocol;
4. Redis may assist with short-lived coordination/replay controls but is not the sole durable registry authority;
5. browser-generated, hash-derived, or payload-derived references remain prohibited.

The proposal intentionally does not select the exact private storage technology, network transport, secret authority, credentials, or production rollout.

No concrete issuer/resolver implementation should be merged until the proposal is reviewed and accepted or revised. The accepted decision must still identify:

1. the public/governance object that causes each reference type to be issued;
2. the system of record for the public-safe reference registration;
3. the private-side mechanism that can resolve the reference without exposing private contents to public;
4. tenant/user/environment authorization rules;
5. lifecycle rules: creation, expiry, revocation, deletion, and replay policy;
6. failure and audit behavior;
7. how local development and CI prove default-deny behavior without private source or real secrets;
8. how Real Staging later proves the actual connector independently.

## Migration sequence

1. **Topology review:** approve or revise `OPAQUE_REFERENCE_TOPOLOGY_DECISION_R1.md`.
2. **Public contract:** define a public-safe registry schema and issuer interface with tests; keep it independent of private modules and private payloads.
3. **Private implementation:** implement the corresponding `PrivateReferenceResolver` only in the private repository after the private backing mapping is independently reviewed.
4. **Composition proof:** bind the private provider explicitly in a controlled non-production runtime and prove default deny when absent.
5. **Client API:** add a ref-oriented client method that accepts already-issued `{formation_ref, evidence_ref, context_ref, evaluated_at}` and calls `/cgt/govern/evaluate`.
6. **Legacy migration:** only after issuance/resolution exists, remove raw-score/vector behavior from the legacy browser/router path in controlled slices.
7. **Real Staging:** independently prove the actual connector, credentials, authorization, audit, lifecycle, and failure behavior.

## Current decision state

The repository now has a concrete topology **proposal**, but it remains review-required and non-authoritative. No registry migration, public issuer implementation, private resolver backing mapping, broker transport, or real connector has been approved by this qualification work.

Therefore:

- no reference fabrication is authorized;
- browser/client migration is not yet authorized;
- no private resolver backing store is assumed;
- `runtime_connector_approved=false`;
- `provider_sandbox_proven=false`;
- `operator_network_qos_proven=false`;
- `RepositoryReconciliationComplete=false`;
- `GeneralPackagingComplete=false`;
- `RealStagingQualified=false`;
- `ProductionAuthorityGranted=false`.
