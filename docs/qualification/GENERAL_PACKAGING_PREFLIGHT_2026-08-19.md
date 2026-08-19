# General Packaging Preflight — 2026-08-19

**Stage:** preparation for Phase F / General Packaging  
**Status:** **PREFLIGHT ONLY — REPOSITORY RECONCILIATION STILL OPEN**

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

The release workflow already performs:

- dependency installation;
- commercial release environment gate;
- migration-head check;
- commercial staging-smoke contract;
- focused commercial regression;
- full pytest suite;
- Ruff;
- Bandit;
- `python -m build`;
- `twine check`;
- release artifact upload;
- GitHub release creation after the release gate.

These are useful packaging foundations but do not yet satisfy the complete General Packaging roadmap.

## Packaging defect corrected during reconciliation

A shared canonical resource loader exists at `cgtlib/reference_data.py` and requires `cgtlib.data/reference_scenarios.json`.

The public main baseline lacked the resource package. The qualification branch now adds:

- `cgtlib/data/__init__.py`;
- `cgtlib/data/reference_scenarios.json`;
- source-level reference-data regression tests;
- explicit setuptools package-data declaration for the JSON resource;
- a regression test for the package-data configuration.

This closes the configuration-level risk where source tests could succeed while the built wheel omitted the canonical JSON resource.

A later package-build proof must still inspect/install the built wheel and load the resource from the installed artifact before this item is considered fully package-qualified.

## Remaining packaging gates — repository/CI capable

### P-F1 — package artifact integrity

Required:

- build wheel and sdist from the exact candidate SHA;
- inspect wheel/sdist contents;
- verify `cgtlib/data/reference_scenarios.json` is included;
- install the built wheel into an isolated environment;
- run a smoke import and canonical reference-data load from the installed package;
- run Twine metadata validation;
- record artifact SHA-256 digests.

### P-F2 — dependency/security qualification

Required in the packaging/release candidate pipeline:

- Ruff;
- Flake8;
- Mypy;
- Bandit;
- pip-audit;
- secret scan;
- dependency inventory;
- license inventory.

The current release workflow covers Ruff and Bandit but does not currently show the complete set above.

### P-F3 — SBOM

Required:

- generate a machine-readable SBOM for the exact release artifact/image;
- bind it to source SHA and artifact/image digest;
- retain it with the release evidence bundle.

No implemented SBOM generation artifact was identified during this preflight.

### P-F4 — Docker/package parity

Required:

- build public image;
- build private image after repository reconciliation;
- prove public image excludes private modules;
- prove private image retains the private integration surface;
- record immutable image digests;
- verify startup/health smoke in an ephemeral non-production environment.

Real staging remains a later phase; ephemeral image smoke is not Real Staging qualification.

### P-F5 — configuration templates

Required:

- reconcile `.env.example` and `.env.production.example` after public/private parity;
- keep placeholders only, never real credentials;
- document required versus optional settings;
- document environment separation;
- verify default-deny behavior when required authorities are absent.

### P-F6 — migration packaging

Required:

- ship the complete shared migration chain;
- verify exactly one expected head per supported product baseline;
- verify upgrade path;
- verify supported downgrade/rollback behavior;
- verify migration files are present in the package/container as required by deployment tooling.

### P-F7 — documentation package

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

The repository contains substantial historical readiness/deployment documentation, but this preflight did not identify a complete release-oriented manual set satisfying all items as one maintained package.

### P-F8 — terminology and obsolete-file cleanup

Required:

- remove temporary/superseded artifacts only after evidence retention needs are checked;
- normalize current product terminology;
- ensure stale transition reports are clearly historical and cannot override current authority;
- ensure release documentation points to the canonical readiness roadmap and current evidence bundle.

## Release workflow gap summary

Current release workflow: strong partial foundation.

Still to add or independently prove before packaging closure:

- Flake8;
- Mypy;
- pip-audit;
- secret scan;
- dependency inventory;
- license inventory;
- SBOM;
- wheel-resource installed-package smoke;
- public/private Docker image qualification;
- immutable image/package digest evidence;
- complete release-oriented operational manual set.

## Phase boundary

General Packaging may be prepared now, but it must not be declared complete until repository reconciliation has been applied and both public/private build boundaries are qualified.

Real environment tests documented in `DEFERRED_REAL_ENVIRONMENT_READINESS_PROOFS_2026-08-19.md` remain outside this preflight and are not waived.

Current state:

`RepositoryReconciliationComplete=false`

`GeneralPackagingComplete=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
