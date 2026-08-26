# Release Notes — Processual Maestro Kernel v2.0.0 Qualification Branch

> **QUALIFICATION NOTES — NOT A RELEASE OR PRODUCTION AUTHORITY STATEMENT**
>
> This branch is under governed qualification. Historical release language has been reconciled to the current public/private trust-boundary, packaging, and visual-qualification model.

## Current focus

The current branch coordinates:

- public/private mathematical trust-boundary qualification;
- commercial entitlement/quota/runtime qualification;
- CAMARA non-real-environment qualification;
- governed legacy-component quarantine and compatibility retirement;
- public browser/security contract qualification;
- release-truth reconciliation;
- preparation for comprehensive Visual Qualification Gate V1 (VQ-1);
- later Real Staging and controlled release qualification.

## Public build profile

The public repository contains governance, orchestration, authentication, commercial contracts, shared-safe adapters, and fail-closed public boundary code. Proprietary mathematical implementation remains private.

Protected mathematical operations must not silently fall back to public approximations. When the approved private evaluation runtime is unavailable, protected operations fail closed through generic public-safe error contracts.

Public-to-private requests are bounded to opaque references and evaluation time. Private-to-public results are limited to the approved sanitized six-field decision contract.

Concrete opaque-reference issuance/resolution and private runtime connectivity remain unapproved until their architecture and backing topology are separately reviewed and qualified.

## Packaging and Docker

The current public Docker qualification is defined by the repository's current `Dockerfile` and exact-head CI evidence. Historical descriptions of `public`/`full` Docker targets or shipping proprietary private modules in a combined image are not current release authority.

Public-image qualification includes private-path leak checks, SBOM generation/verification, source/runtime quarantine controls, non-root execution, and fail-closed public behavior. An immutable image digest must eventually become the promotion authority; mutable tags are not sufficient for Real Staging/RC/pilot/GA promotion.

## Browser and visual qualification

Current rendered HTTP/security coverage is **VQ-0 contract qualification**. It checks active public entry surfaces, Console delivery controls, Admin DOM/no-store contracts, security headers, quarantined legacy assets, and pinned Chart.js delivery.

A separate **Visual Qualification Gate V1 (VQ-1)** is the next near-term UI gate after release-truth reconciliation and before Real Staging. VQ-1 will run and present the complete user-visible program for systematic review of every page and active section, declared desktop/narrow viewports, relevant success/error/fail-closed/subscription states, and a screenshot/evidence matrix tied to an exact source SHA.

VQ-1 cannot close with unreviewed user-visible pages or active sections, or with unresolved Blocker/High visual defects.

## Legacy and compatibility control

Legacy raw-math browser sources remain quarantined from active delivery and from the public runtime image while retained in source history for review. Compatibility-only routes/modules remain available only where external compatibility has not yet been proven safe to remove; qualification rejects new internal dependencies on those legacy surfaces.

Deletion is evidence-driven and never inferred from naming or age.

## CAMARA

CAMARA QoD remains qualified only for the currently exercised non-real/mock interoperability scope. It does not prove full operator/provider conformance, does not prove operator-network QoS, does not waive unresolved API gaps, and does not grant Real Staging or production authority.

## Release truth and licensing

Historical static test counts, coverage percentages, endpoint totals, or past readiness labels are not current release evidence. Current status must be taken from exact-head CI and governed qualification artifacts.

The repository's product-distribution license remains an explicit owner/legal decision. README or dependency license statements alone do not establish external distribution authority. Root license artifact, package metadata, and documentation must be synchronized before external distribution.

## Remaining gates

Before production authority can be considered, the program still requires release-truth closure, VQ-1, opaque-reference topology approval and implementation, final public/private boundary migration, explicit license resolution, immutable release artifact/digest qualification, Real Staging, secret binding/rotation/audit, migration/backfill/backup/restore rehearsal, commercial E2E, load/concurrency/security/observability/rollback evidence, real provider/operator proof as applicable, release-candidate qualification, and a controlled pilot.

## Authority

This document does not grant staging, RC, pilot, GA, or production authority.

- `GeneralPackagingComplete=false`
- `PrivateRuntimeAuthorityGranted=false`
- `runtime_connector_approved=false`
- `provider_sandbox_proven=false`
- `operator_network_qos_proven=false`
- `RealStagingQualified=false`
- `ProductionAuthorityGranted=false`
