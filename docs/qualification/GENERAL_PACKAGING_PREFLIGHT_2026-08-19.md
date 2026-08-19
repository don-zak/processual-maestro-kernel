# General Packaging Preflight — 2026-08-19

**Stage:** preparation for Phase F / General Packaging  
**Status:** **PREFLIGHT ADVANCED — REPOSITORY RECONCILIATION STILL OPEN**

## Purpose

Inventory packaging work that is already implemented and the remaining non-real-environment packaging gates that can be completed before Real Staging.

This preflight does not skip the required public/private repository reconciliation phase. It prepares the next phase while parity porting remains pending.

## Existing packaging foundations

The public repository already has:

- `pyproject.toml` with setuptools build metadata;
- Python 3.14 package definition and optional dependency groups;
- package discovery for `processual_kernel`, `cgtlib`, and `processual_api`;
- Dockerfile;
- release workflow;
- changelog;
- deployment/readiness documents;
- security/lint/test tooling dependencies.

The qualification branch release workflow now includes:

- dependency installation;
- commercial release environment gate;
- migration-head verification/application and subscription-runtime backfill checks;
- commercial staging-smoke contract;
- focused commercial regression;
- full pytest suite;
- Ruff;
- Flake8 critical-error gate;
- focused Mypy gate aligned with public CI;
- Bandit;
- pip-audit vulnerability gate;
- `python -m build`;
- built-wheel resource inspection;
- isolated installed-wheel reference-data smoke;
- `twine check`;
- source/artifact/dependency/license evidence inventory;
- CycloneDX JSON dependency SBOM generation;
- retained release evidence and distribution artifacts;
- GitHub release creation only after the release gate.

These are strong packaging foundations but do not yet satisfy the complete General Packaging roadmap.

## Packaging defect corrected during reconciliation

A shared canonical resource loader exists at `cgtlib/reference_data.py` and requires `cgtlib.data/reference_scenarios.json`.

The public main baseline lacked the resource package. The qualification branch now adds:

- `cgtlib/data/__init__.py`;
- `cgtlib/data/reference_scenarios.json`;
- source-level reference-data regression tests;
- explicit setuptools package-data declaration for the JSON resource;
- a regression test for the package-data configuration;
- release-workflow inspection proving the JSON is inside the built wheel;
- an isolated venv smoke that installs the wheel and loads the canonical data from the installed artifact.

Configuration and workflow contracts are implemented. Actual tag/release execution evidence is still required before this is considered release-qualified.

## P-F1 — package artifact integrity

**Implementation status:** substantially wired; execution evidence pending.

The release workflow now:

- builds wheel and sdist;
- verifies the canonical CGT resource is inside the wheel;
- installs the wheel in an isolated environment;
- loads canonical reference data from that installed artifact;
- runs Twine metadata validation;
- records SHA-256 and sizes for built artifacts in `release-evidence/release-inventory.json`.

Still required for closure:

- successful execution on an exact packaging/release candidate SHA;
- retained artifact/evidence digests from that run.

## P-F2 — dependency/security qualification

**Implementation status:** advanced.

The release workflow now includes:

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
- review of packages with missing/ambiguous license metadata.

## P-F3 — SBOM

**Implementation status:** wired, execution evidence pending.

The release workflow now uses the already-installed PyPA `pip-audit` tooling to emit:

`release-evidence/python-environment.cdx.json`

in CycloneDX JSON format after the vulnerability gate succeeds.

The separate `release-inventory.json` remains explicitly labeled as dependency/license evidence rather than an SBOM.

Still required:

- successful SBOM generation on the exact release candidate;
- bind/retain it beside exact source and package/image digests;
- later add/verify container-image SBOM coverage when Docker image qualification is performed.

## P-F4 — Docker/package parity

**Status:** open; depends on repository reconciliation.

Required:

- build public image;
- build private image after repository reconciliation;
- prove public image excludes private modules;
- prove private image retains the private integration surface;
- record immutable image digests;
- verify startup/health smoke in an ephemeral non-production environment.

Real staging remains a later phase; ephemeral image smoke is not Real Staging qualification.

## P-F5 — configuration templates

**Status:** open after public/private parity.

Required:

- reconcile `.env.example` and `.env.production.example`;
- keep placeholders only, never real credentials;
- document required versus optional settings;
- document environment separation;
- verify default-deny behavior when required authorities are absent.

## P-F6 — migration packaging

**Status:** public chain advanced; private parity still open.

Required:

- ship the complete shared migration chain;
- verify exactly one expected head per supported product baseline;
- verify upgrade path;
- verify supported downgrade/rollback behavior;
- verify migration files are present in the package/container as required by deployment tooling;
- reconcile the currently absent private Alembic chain during repository parity work.

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
- release notes/changelog reconciliation.

The repository contains substantial historical readiness/deployment documentation, but a complete maintained release-oriented manual set has not yet been proven.

## P-F8 — terminology and obsolete-file cleanup

**Status:** open.

Required:

- remove temporary/superseded artifacts only after evidence-retention needs are checked;
- normalize current product terminology;
- ensure stale transition reports are clearly historical and cannot override current authority;
- ensure release documentation points to the canonical readiness roadmap and current evidence bundle.

## Remaining packaging gap summary

The major repository/CI-capable gaps are now:

1. secret scan gate;
2. review/normalization of ambiguous dependency license metadata;
3. public/private Docker image qualification after parity port;
4. immutable image digest + container SBOM evidence;
5. complete release-oriented operational manuals;
6. terminology/obsolete-file cleanup;
7. successful execution evidence for the newly wired release gates.

## Phase boundary

General Packaging may continue in preparation, but it must not be declared complete until repository reconciliation has been applied and both public/private build boundaries are qualified.

Real-environment tests documented in `DEFERRED_REAL_ENVIRONMENT_READINESS_PROOFS_2026-08-19.md` remain outside this preflight and are not waived.

Current state:

`RepositoryReconciliationComplete=false`

`GeneralPackagingComplete=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
