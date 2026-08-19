# Opaque Reference Topology Decision — R1

**Status:** PROPOSED — REVIEW REQUIRED — NO RUNTIME AUTHORITY  
**Date:** 2026-08-19

## Decision objective

Advance opaque-reference work from an abstract requirement to a concrete, reviewable topology without fabricating a resolver, private backing store, or production authority.

This record does not grant `runtime_connector_approved`, `PrivateRuntimeAuthorityGranted`, `RealStagingQualified`, or `ProductionAuthorityGranted`.

## Constraints already established

The public evaluation request contains only:

- `formation_ref`
- `evidence_ref`
- `context_ref`
- `evaluated_at`

The public response remains exactly:

- `existence_rank`
- `dominant_constraint`
- `next_gate`
- `confidence_band`
- `explanation_code`
- `policy_version`

References must never encode, hash, serialize, or otherwise derive from raw scores, vectors, equations, thresholds, calibration values, private intermediates, answer text, or private implementation identifiers.

## Repository/deployment evidence considered

Current qualification work treats PostgreSQL/Cloud SQL as the durable commercial/runtime source of truth and Redis as coordination/cache rather than irreplaceable truth. Current source review did not establish an existing reviewed opaque-reference registry that already satisfies type, tenant, environment, expiry, revocation, and private-resolution requirements.

Therefore this decision proposes a new shared-safe metadata registry rather than repurposing an unrelated cache or inventing reference semantics in the browser.

## Proposed topology

### 1. Public-safe reference registry

Use durable PostgreSQL persistence for **reference metadata only**. A registry record may contain only fields independently safe for the public trust domain, for example:

- opaque random reference token or token digest used for indexed lookup;
- reference type: `formation`, `evidence`, or `context`;
- tenant/customer scope identifier that is already public-safe;
- subject/user scope identifier where required;
- environment scope;
- public-safe resolution locator or broker routing key that does not reveal private mathematical contents;
- created timestamp;
- expiry timestamp where applicable;
- revoked timestamp/reason code where applicable;
- single-use/replay policy marker where required;
- public-safe issuer/audit identifiers.

The registry MUST NOT contain resolved private payloads, raw mathematical inputs, score vectors, private object serialization, equations, calibration data, or private implementation names.

### 2. Public issuer service

A dedicated public-safe issuer should:

1. authenticate and authorize issuance;
2. validate tenant, subject, environment, and reference type;
3. generate a cryptographically random bounded opaque token;
4. register only shared-safe metadata;
5. apply expiry/revocation/replay policy;
6. audit issuance without private payload contents;
7. return the opaque token only after persistence succeeds.

Possession of a token alone must never authorize cross-tenant or cross-subject use.

### 3. Controlled private resolution

The private trust domain should implement the existing `PrivateReferenceResolver` protocol through an explicitly approved controlled connector or broker.

Resolution should:

1. receive the already-authorized reference context through the controlled boundary;
2. validate type, tenant/subject scope, environment, lifecycle, and replay policy;
3. use the public-safe routing metadata only to locate the corresponding private-side object;
4. resolve and transform the private object entirely inside the private trust domain;
5. invoke private mathematical execution there;
6. return only the exact six sanitized decision fields.

Resolved private objects must never cross back into the public runtime.

### 4. Broker boundary

The preferred integration shape is a controlled broker/service boundary rather than direct public database access into private persistence.

The broker must expose no generic private lookup endpoint. It should accept only typed reference-resolution/evaluation operations required by the sanctioned boundary and must collapse failures to generic unavailable/contract errors.

## Why Redis is not selected as registry authority

Redis may support short-lived coordination or replay controls, but it must not be the sole durable authority for reference registration because current release architecture treats it as cache/coordination rather than irreplaceable system of record.

## Why browser-generated references are prohibited

The browser does not own the system of record and cannot prove resolvability, tenant binding, type binding, lifecycle, or private authorization. Client-generated hashes or encoded payloads would create tokens that look opaque but are not controlled references.

## Required data model properties before implementation

Any concrete registry migration must prove:

- cryptographically random tokens with sufficient entropy;
- bounded syntax compatible with the public boundary;
- uniqueness/collision handling;
- indexed lookup without logging the raw token unnecessarily;
- reference type constraint;
- tenant/customer constraint;
- optional subject/user constraint;
- environment constraint;
- creation and expiry timestamps;
- revocation lifecycle;
- replay/single-use semantics where needed;
- audit events that contain no private payload;
- deletion/retention policy;
- transactional issuance behavior.

## Required API behavior before client migration

A future public issuance API must be separate from evaluation and must fail closed for:

- unauthorized tenant/subject;
- unsupported reference type;
- invalid environment;
- expired or revoked lifecycle;
- persistence unavailable;
- broker unavailable;
- type confusion;
- cross-tenant resolution attempts.

Public responses must not reveal whether a private object exists.

## Required test matrix

Before runtime approval, tests must cover at minimum:

- formation/evidence/context happy paths;
- type confusion across all reference types;
- cross-tenant reference use;
- cross-subject reference use where subject scope applies;
- environment confusion;
- expiry;
- revocation;
- replay/single-use behavior where configured;
- unknown token;
- registry unavailable;
- private broker unavailable;
- private resolver failure redaction;
- exact six-field sanitized result;
- logs/errors/traces contain no raw private contents;
- public runtime cannot import or discover private modules;
- default deny when no private provider/resolver is bound.

## Implementation sequence

1. Architecture/security review of this proposed topology.
2. Define the shared-safe registry schema and public issuer interface in the public repository.
3. Add migration and persistence tests without any private payload fixtures.
4. Implement private resolver/broker only in the private repository after the private backing mapping is independently approved.
5. Prove composition in a controlled non-production environment.
6. Add ref-oriented browser/client flow using already-issued references.
7. Remove legacy raw-score/vector browser/router/report paths in controlled slices.
8. Prove the real connector, secret delivery, authorization, audit, lifecycle, failure behavior, and rollback in Real Staging.

## Explicit non-decisions

This proposal does **not** decide:

- the exact private storage technology;
- the exact network transport between public and private trust domains;
- secret-provider authority;
- production credentials;
- private mathematical object schema;
- production rollout timing.

Those decisions require separate evidence and approval.

## Authority state after this record

All launch and runtime authority flags remain unchanged and false. This document is a reviewable design advancement only; it is not implementation or environment proof.
