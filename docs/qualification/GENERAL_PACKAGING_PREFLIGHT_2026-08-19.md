# General Packaging Preflight — 2026-08-19

**Stage:** preparation for Phase F / General Packaging  
**Status:** **PREFLIGHT ADVANCED — EXACT-SOURCE PUBLIC ARTIFACT GATES GREEN; TRUST-BOUNDARY RECONCILIATION STILL OPEN**

## Purpose

Inventory packaging work already implemented and the remaining non-real-environment gates that can be completed before Real Staging.

This preflight does not skip public/private trust-boundary reconciliation. Repository mirroring is not a prerequisite and is not a goal. Packaging may close only after the public artifact is proven independent of proprietary private implementation and the private artifact is qualified separately in its controlled context.

## Existing packaging foundations

The public repository already has:

- `pyproject.toml` with setuptools build metadata;
- Python package definition and optional dependency groups;
- package discovery for `processual_kernel`, `cgtlib`, and `processual_api`;
- public-only Dockerfile;
- release and packaging-qualification workflows;
- changelog and readiness documentation;
- security/lint/test tooling dependencies.

The qualification branch packaging/release work includes:

- dependency installation;
- commercial release environment gate;
- migration-head verification/application and subscription-runtime backfill checks;
- commercial staging-smoke contract;
- focused commercial regression;
- full pytest suite in the release workflow;
- Ruff, Flake8, focused Mypy, Bandit and pip-audit;
- dedicated high-confidence secret scanning;
- `python -m build` and `twine check`;
- built-wheel resource/private-path inspection;
- isolated installed-wheel reference-data and trust-boundary smoke;
- source/artifact/dependency/license evidence inventory;
- CycloneDX JSON dependency SBOM generation;
- retained release evidence/distributions;
- public/private trust-boundary regression in Packaging Qualification;
- public-only Docker build and ephemeral trust-boundary smoke.

These are strong foundations but do not yet satisfy complete General Packaging closure.

## Historical exact-head qualification evidence

Evidence-bearing public source SHA:

`d22238a27462429094003ed71d4c4ae6721e7edf`

Successful PR-triggered workflows for that exact SHA:

- Packaging Qualification run `32249985813` / run number `116` — **SUCCESS**;
- Public Docker Build run `32249985849` / run number `12` — **SUCCESS**;
- CAMARA Public Source Contracts run `32249985940` / run number `182` — **SUCCESS**;
- Sandbox Integration Qualification run `32249985895` / run number `320` — **SUCCESS**.

Packaging Qualification run 116 completed successfully through:

- 48 focused packaging/trust-boundary regression tests;
- Ruff;
- Flake8 critical errors;
- focused Mypy;
- high-confidence secret scan;
- pip-audit;
- wheel and sdist build;
- Twine metadata validation;
- canonical resource/private-path wheel inspection;
- isolated installed-wheel trust-boundary smoke;
- release evidence inventory generation;
- CycloneDX Python dependency SBOM generation;
- packaging evidence upload.

Public Docker Build run 12 completed successfully through:

- ephemeral public image build;
- no GHCR login or image push on the PR event;
- trust-boundary smoke proving the public container has no private implementation modules and protected evaluation fails closed without private-provider authority;
- ephemeral image identity recording.

## Current boundary/runtime qualification evidence

Evidence-bearing public source SHA:

`cec49f8eeec7eb5ef0ca55c103ef301462b4df40`

Successful PR-triggered workflows for that exact SHA:

- Packaging Qualification run `32261096359` / run number `143` — **SUCCESS**;
- Public Docker Build run `32261096365` / run number `30` — **SUCCESS**;
- CAMARA Public Source Contracts run `32261096358` / run number `200` — **SUCCESS**;
- Sandbox Integration Qualification run `32261096380` / run number `338` — **SUCCESS**.

Packaging Qualification run 143 completed successfully through focused trust-boundary regression, Ruff, Flake8, focused Mypy, high-confidence secret scanning, pip-audit, wheel/sdist build, Twine metadata validation, canonical resource/private-path wheel inspection, dependency-free installed-wheel fail-closed smoke, release evidence inventory, CycloneDX Python dependency SBOM generation, and evidence upload.

The dependency-free installed-wheel smoke intentionally proves only dependency-independent package behavior. FastAPI/Starlette-dependent HTTP composition is not imported in that `--no-deps` environment. Instead, wheel archive inspection proves `processual_api/integrations/private_evaluation_http.py` and `processual_api/integrations/private_evaluation_runtime.py` are present, while Public Docker Build run 30 provides the full-runtime proof that `/cgt/govern/evaluate` is registered and that no private provider is auto-bound by default.

The canonical public mediation now includes bounded reference-only requests, explicit app-state private-provider injection, default-deny provider lookup, exact six-field sanitized responses, generic boundary errors, and quota enforcement at the public router-composition edge. This does not supply opaque reference issuance/resolution itself and does not authorize private runtime use.

Private Draft PR #49 exact head `5138a8052252d4ce65124c2bb9ac4275cfcbb5f8` separately passed its seven current CI/boundary workflows. That evidence remains inside the private trust-domain qualification path and does not substitute for private image qualification.

All evidence in this section is non-real-environment build/packaging evidence only. It is not Real Staging qualification and grants no runtime/private-provider/operator-network/production authority.

## Packaging defect corrected during reconciliation

A shared canonical resource loader exists at `cgtlib/reference_data.py` and requires `cgtlib.data/reference_scenarios.json`.

The qualification branch restores and verifies:

- `cgtlib/data/__init__.py`;
- `cgtlib/data/reference_scenarios.json`;
- source-level reference-data regression tests;
- explicit setuptools package-data declaration;
- package-data configuration regression;
- wheel inspection proving the JSON resource is included;
- isolated installed-wheel loading of the canonical data.

This canonical resource is classified shared/public-safe product data, not private mathematical implementation.

## P-F0 — public/private trust-boundary packaging gate

**Status:** public-side exact-source gate successful; repository-boundary closure still blocked by legacy router/client debt, opaque reference issuance/resolution design, and remaining review.

This gate is mandatory and precedes package closure.

Public artifact requirements:

1. no `cgtlib/private/` in source/package/image;
2. no `processual_api/private_integrations/` in source/package/image;
3. public source must not import or discover either private implementation path;
4. public `cgtlib` must import with private modules absent and explicitly report `_HAS_PRIVATE=False`;
5. protected mathematical operations must fail closed rather than silently reimplement private execution;
6. private-provider exceptions must cross the boundary only as generic public errors;
7. the allowed private decision result is exactly the approved sanitized contract;
8. the public governor must not run its legacy local mathematical pipeline as a fallback;
9. public policy/repair orchestration may consume a sanitized private decision without receiving raw private vectors, weights, thresholds, calibration or intermediate state;
10. installed-wheel/container smoke must prove the private implementation packages cannot be imported.

API/log/evidence requirements:

- no private equations or mathematical internals in responses;
- no raw private vectors/intermediate state in logs, traces, telemetry or retained evidence;
- no private exception text or stack detail may be surfaced through public errors;
- no packaging evidence job may extract private source merely to prove exclusion.

Private artifact requirements are separate:

- private implementation remains inside the private trust domain;
- private adapter tests prove only the six approved sanitized output fields cross the boundary;
- private adapter errors remain generic;
- private full regression and boundary checks must pass;
- private source itself is not copied into public CI evidence.

Private Draft PR #49 provides successful private-side boundary qualification checks, but it remains Draft and is not merged. Public packaging evidence does not substitute for separate private image qualification.

Any violation of P-F0 blocks `GeneralPackagingComplete=true` regardless of all other packaging results.

## P-F1 — package artifact integrity

**Implementation status:** current exact-source packaging gate successful; release-candidate binding/review pending.

The packaging/release workflows now:

- build wheel and sdist;
- verify canonical shared resources inside the wheel;
- verify private implementation paths are absent from the public wheel;
- verify the canonical public HTTP/runtime mediation modules are present in the wheel without requiring their optional dependencies in the no-deps smoke;
- install the wheel in an isolated dependency-free environment;
- verify reference data and core fail-closed trust-boundary behavior from the installed artifact;
- run Twine metadata validation;
- record SHA-256 and sizes for built artifacts in `release-evidence/release-inventory.json`.

Current evidence-bearing Packaging Qualification run 143 passed these controls for source SHA `cec49f8eeec7eb5ef0ca55c103ef301462b4df40`.

Still required for closure:

- bind retained artifact/evidence digests to the designated release candidate;
- independent review that the resulting public artifact contains no prohibited private implementation;
- final release-candidate gate execution.

## P-F2 — dependency/security qualification

**Implementation status:** current exact-source public gate successful; final review pending.

Current gates include:

- Ruff;
- Flake8;
- Mypy;
- Bandit in the release workflow;
- pip-audit;
- dedicated high-confidence secret scan;
- installed dependency inventory;
- installed package license metadata inventory.

Packaging Qualification run 143 passed Ruff, Flake8, Mypy, secret scan and pip-audit on source SHA `cec49f8eeec7eb5ef0ca55c103ef301462b4df40`.

Still required:

- review of packages with missing/ambiguous license metadata;
- review that security/error handling cannot leak private provider internals across all remaining operational routes;
- final release-candidate execution including the broader release security gate.

## P-F3 — SBOM

**Implementation status:** current exact-source Python environment SBOM successful; container SBOM open.

The packaging/release workflows emit:

`release-evidence/python-environment.cdx.json`

in CycloneDX JSON format. Packaging Qualification run 143 generated and retained this evidence successfully.

Still required:

- bind/retain the Python SBOM beside exact release-candidate source and package/image digests;
- container-image SBOM for the qualified public image;
- private image SBOM generated only in the controlled private context, with no private source content copied to public evidence.

## P-F4 — Docker/package boundary qualification

**Status:** current public ephemeral image build/trust-boundary smoke successful; container SBOM and private-side image qualification remain open.

The public repository is now public-image-only:

- no public Docker `private` target exists;
- the public Docker workflow exposes only the `public` build target;
- PR builds are ephemeral and are not pushed;
- tag-triggered publishing applies only to the public image;
- private image build/qualification is explicitly outside the public repository and belongs to private CI/environment.

Public Docker Build run 30 succeeded for source SHA `cec49f8eeec7eb5ef0ca55c103ef301462b4df40`, including full-runtime canonical route registration, default-deny private-provider state, container trust-boundary smoke, and image identity recording.

Still required for closure:

- generate and retain a container-image SBOM for the qualified public image;
- bind an immutable qualified public image digest to the release candidate;
- qualify the private image separately in private CI/environment;
- verify the private image retains required private execution modules without exporting private source or mathematical internals into public evidence;
- complete any additional non-production startup/health checks required for the designated release candidate.

Real staging remains a later phase; ephemeral image smoke is not Real Staging qualification.

## P-F5 — configuration templates

**Status:** open after trust-boundary review.

Required:

- reconcile `.env.example` and `.env.production.example` only for public/shared settings;
- keep placeholders only, never real credentials;
- document required versus optional settings;
- document environment separation;
- document private-provider binding as an opaque controlled dependency, never a private source path;
- verify default-deny/fail-closed behavior when required authorities are absent.

## P-F6 — migration packaging

**Status:** public product chain advanced; deployment ownership review remains open.

Required:

- ship the complete migration chain for deployments that host public product persistence;
- verify exactly one expected head per supported public product baseline;
- verify upgrade and supported rollback behavior;
- verify migration files are present in the deployment artifact as required;
- do not mirror the public migration chain into the private mathematical runtime unless a reviewed deployment topology explicitly requires public persistence to be co-located there.

## P-F7 — documentation package

**Status:** incomplete.

Required before release-candidate closure:

- operator guide;
- administrator guide;
- customer guide;
- safe configuration guide;
- deployment guide;
- migration guide;
- backup/restore manual;
- rollback manual;
- incident-response manual;
- public/private trust-boundary operations guide;
- release notes/changelog reconciliation.

The trust-boundary guide must state that operators must not place private source, mathematical internals, raw private vectors, or private exception details in public incident artifacts.

## P-F8 — terminology and obsolete-file cleanup

**Status:** open.

Required:

- replace stale "parity" language where it implies repository mirroring;
- retain historical filenames only when needed for evidence traceability and mark superseding records clearly;
- remove temporary/superseded artifacts only after evidence-retention needs are checked;
- normalize current product terminology;
- ensure stale transition reports cannot override current authority;
- ensure release documentation points to the canonical readiness roadmap and current trust-boundary evidence.

## Remaining packaging gap summary

Major remaining gates are:

1. design/proof of opaque reference issuance and private-side resolution topology, followed by migration of remaining operational paths that expose raw scores/vectors instead of sanitized decisions, especially `processual_api/routers/cgt_governor.py` and dependent client/report surfaces;
2. dependency-license and private-error-surface review;
3. public container-image SBOM and immutable release-candidate image digest;
4. separate private image qualification in private CI/environment;
5. configuration-template reconciliation;
6. complete release-oriented operational manuals;
7. terminology/obsolete-file cleanup;
8. final exact release-candidate release-gate evidence.

## Phase boundary

General Packaging has successful exact-source public package/image qualification evidence and separate successful private boundary CI evidence, but it must not be declared complete until trust-boundary reconciliation and remaining required public/private artifact qualification have succeeded.

Real-environment tests documented in `DEFERRED_REAL_ENVIRONMENT_READINESS_PROOFS_2026-08-19.md` remain outside this preflight and are not waived.

Current state:

`RepositoryReconciliationComplete=false`

`GeneralPackagingComplete=false`

`PrivateRuntimeAuthorityGranted=false`

`runtime_connector_approved=false`

`provider_sandbox_proven=false`

`operator_network_qos_proven=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
