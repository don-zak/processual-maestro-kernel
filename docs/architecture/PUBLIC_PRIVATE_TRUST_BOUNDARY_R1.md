# Public / Private Mathematical Trust Boundary — R1

## Status

**Architecture invariant — mandatory for repository reconciliation, packaging, staging, and production readiness.**

This document does not grant staging, production, connector, or private-runtime authority.

## Purpose

The private repository is an isolated proprietary execution environment for protected mathematical material. The public repository is the governance, orchestration, product, integration, audit, quota, policy, and sanitized contract surface.

Repository reconciliation must preserve this separation. The goal is not to make the two repositories source-identical.

## Protected private material

The following classes of information must remain inside the private repository/runtime and must not be copied, serialized, logged, traced, packaged, or otherwise exposed through the public surface:

- proprietary equations and mathematical implementations;
- weights and weighting schemes;
- thresholds and decision boundaries;
- calibration values, calibration algorithms, and fitted parameters;
- private vectors, intermediate scores, internal state, and raw mathematical outputs;
- private implementation module names when they reveal protected topology beyond an approved adapter identifier;
- private source paths, stack traces, exception payloads, or debug representations;
- secrets, credentials, private configuration, and private-only datasets.

## Public responsibilities

The public repository remains authoritative for:

- governance and admission decisions;
- task orchestration;
- entitlement and quota enforcement;
- approval gates;
- operator/provider integration governance;
- audit and evidence contracts;
- product, billing, administration, and lifecycle workflows;
- sanitized request/response schemas;
- fail-closed handling when private evaluation is unavailable.

Public functionality must remain buildable and testable without private source trees.

## Boundary shape

The public side may send only bounded opaque references and execution metadata required by the approved contract. It must not send or embed proprietary mathematical values as a substitute for private resolution.

The private side may return only an approved sanitized decision surface. R1 permits exactly:

1. `existence_rank`
2. `dominant_constraint`
3. `next_gate`
4. `confidence_band`
5. `explanation_code`
6. `policy_version`

No additional field is implicitly approved.

## Composition rule

The public contract does not import, discover, locate, or dynamically load private implementation modules.

The private runtime is responsible for composing its proprietary provider behind the public-safe protocol/adapter contract. Private source knowledge therefore flows inward on the private side only.

## Failure rule

Provider failure must fail closed.

Public errors must be generic and must not preserve or expose private exception text, stack information, paths, parameters, values, equations, weights, thresholds, calibration state, or intermediate results.

## Packaging rule

A public wheel/image must not contain:

- `cgtlib/private/`;
- `processual_api/private_integrations/`;
- any later private-only source tree introduced under an equivalent protected boundary.

The private package/image may contain those protected paths, but public build artifacts and evidence bundles must remain sanitized.

## Logging and telemetry rule

Public logs, traces, metrics, audit records, browser responses, API responses, evidence bundles, and support diagnostics may record safe identifiers, opaque references, approved decision fields, status codes, timings, and policy versions only.

They must never include protected mathematical content or raw private exceptions.

## Reconciliation rule

Every public/private drift item must be classified as one of:

- **SHARED-PUBLIC-SAFE** — may converge across repositories;
- **PRIVATE-PRESERVE** — must remain private and absent from public;
- **BOUNDARY-ADAPTER** — contract may be shared, but proprietary provider composition remains private;
- **ARCHITECTURAL-VIOLATION** — mixes protected private mathematics into public governance/product code and must be split before porting.

A repository-wide copy or overwrite is prohibited.

## Required qualification evidence

Before repository reconciliation can close, evidence must prove:

- private source trees absent from public source and public artifacts;
- public runtime source does not import private implementation modules;
- boundary request is reference-only and bounded;
- boundary result fields are exactly the approved sanitized set;
- malformed or expanded private results fail closed;
- provider exceptions cannot leak their messages or exception context;
- private adapter tests preserve proprietary-field exclusions;
- public build remains functional without the private runtime;
- private build retains private functionality without exposing protected source through public interfaces.

## Authority state

`PublicPrivateTrustBoundaryDefined=true`

`PrivateMathematicalContentPubliclyApproved=false`

`RepositoryReconciliationComplete=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
