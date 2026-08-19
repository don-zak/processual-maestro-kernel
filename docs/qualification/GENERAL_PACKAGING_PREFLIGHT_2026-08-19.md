# General Packaging Preflight — 2026-08-19

**Stage:** preparation for Phase F / General Packaging  
**Status:** **PREFLIGHT ADVANCED — TRUST-BOUNDARY RECONCILIATION STILL OPEN**

## Purpose

Inventory packaging work already implemented and the remaining non-real-environment gates that can be completed before Real Staging.

This preflight does not skip public/private trust-boundary reconciliation. Repository mirroring is not a prerequisite and is not a goal. Packaging may close only after the public artifact is proven independent of proprietary private implementation and the private artifact is qualified separately in its controlled context.

## Existing packaging foundations

The public repository already has:

- `pyproject.toml` with setuptools build metadata;
- Python package definition and optional dependency groups;
- package discovery for `processual_kernel`, `cgtlib`, and `processual_api`;
- Dockerfile;
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
- `python -m build` and `twine check`;
- built-wheel resource inspection;
- isolated installed-wheel reference-data smoke;
- source/artifact/dependency/license evidence inventory;
- CycloneDX JSON dependency SBOM generation;
- retained release evidence/distributions;
- public/private trust-boundary regression in Packaging Qualification.

These are strong foundations but do not yet satisfy complete General Packaging closure.

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

**Status:** implemented substantially; exact-head execution/review still required.

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
10. installed-wheel smoke must prove the private implementation packages cannot be imported.

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

Any violation of P-F0 blocks `GeneralPackagingComplete=true` regardless of all other packaging results.

## P-F1 — package artifact integrity

**Implementation status:** substantially wired; exact-candidate evidence pending.

The packaging/release workflows now:

- build wheel and sdist;
- verify canonical shared resources inside the wheel;
- verify private implementation paths are absent from the public wheel;
- install the wheel in an isolated environment;
- verify reference data and trust-boundary behavior from the installed artifact;
- run Twine metadata validation;
- record SHA-256 and sizes for built artifacts in `release-evidence/release-inventory.json`.

Still required for closure:

- successful execution on an exact packaging/release candidate SHA;
- retained artifact/evidence digests from that run;
- independent review that the resulting public artifact contains no prohibited private implementation.

## P-F2 — dependency/security qualification

**Implementation status:** advanced.

Current gates include:

- Ruff;
- Flake8;
- Mypy;
- Bandit;
- pip-audit;
- installed dependency inventory;
- installed package license metadata inventory.

Still required:

- dedicated secret scan gate;
- successful exact-candidate execution evidence;
- review of packages with missing/ambiguous license metadata;
- review that security/error handling cannot leak private provider internals.

## P-F3 — SBOM

**Implementation status:** Python environment SBOM wired; broader artifact evidence open.

The release workflow emits:

`release-evidence/python-environment.cdx.json`

in CycloneDX JSON format.

Still required:

- successful generation on the exact release candidate;
- binding/retention beside exact source and package/image digests;
- container-image SBOM for qualified public image;
- private image SBOM generated only in the controlled private context, with no private source content copied to public evidence.

## P-F4 — Docker/package boundary qualification

**Status:** open; depends on trust-boundary reconciliation, not source parity.

Required:

- build the public image;
- prove public image excludes private modules and private source;
- verify public startup/health without private implementation installed;
- verify protected evaluation fails closed when private provider authority is absent;
- build/qualify the private image separately in private CI/environment;
- verify the private image retains required private execution modules;
- record immutable image digests without exposing private implementation content;
- perform ephemeral non-production startup/health smoke.

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

1. exact-head green execution of the strengthened Packaging Qualification gate;
2. audit/migration of any remaining operational path that exposes raw scores/vectors instead of sanitized decisions;
3. dedicated secret scan gate;
4. dependency-license review;
5. public/private Docker image qualification under separate trust contexts;
6. immutable image digests and container SBOM evidence;
7. complete release-oriented operational manuals;
8. terminology/obsolete-file cleanup;
9. successful exact-candidate release-gate evidence.

## Phase boundary

General Packaging may continue in preparation, but it must not be declared complete until trust-boundary reconciliation and required public/private artifact qualification have succeeded.

Real-environment tests documented in `DEFERRED_REAL_ENVIRONMENT_READINESS_PROOFS_2026-08-19.md` remain outside this preflight and are not waived.

Current state:

`RepositoryReconciliationComplete=false`

`GeneralPackagingComplete=false`

`PrivateRuntimeAuthorityGranted=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
