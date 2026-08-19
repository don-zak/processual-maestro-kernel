# Public / Private Repository Reconciliation Baseline — 2026-08-19

**Stage:** Repository reconciliation  
**Status:** **IN PROGRESS — INVENTORY ONLY, NO SYNC/MERGE PERFORMED**

## Repository identities

Public repository:

`don-zak/processual-maestro-kernel`

Public `main` at baseline:

`a63b4a7d40643a685caeaafc8cbfd11f59e9d544`

Private repository:

`don-zak/processual-maestro-kernel-private`

Private `main` at baseline:

`84e3354cd43802176ee93ed94f72144341c0068b`

## Initial observation

The public main is newer than the private main at this baseline. The two repositories share substantial top-level structure, but they are not byte-identical mirrors and must not be reconciled by blind tree replacement.

Examples already observed:

### Identical/shared top-level files by blob SHA

At least the following baseline files show identical blob SHAs in both repositories:

- `.dockerignore`;
- `.flake8`;
- `.gitattributes`;
- `.pre-commit-config.yaml`;
- `CHANGELOG.md`;
- `CONTRIBUTING.md`;
- `EXTERNAL_READINESS_REPORT.md`.

These are candidates for shared-core invariants.

### Divergent top-level files

The following are already different between public and private baselines:

- `.env.example`;
- `.env.production.example`;
- `.gitignore`;
- `.github/` tree;
- `DEPLOYMENT_EXTERNAL.md`;
- `Dockerfile`.

These differences may be legitimate private-only/runtime differences or stale shared-core drift. They require classification before modification.

## Reconciliation safety rules

1. Do not overwrite the private repository with the public tree.
2. Do not copy private-only integrations into the public repository.
3. Do not infer that a differing file is stale until its role is classified.
4. Public-exclusion rules must remain explicit and testable.
5. Shared files should be reconciled by semantic role and exact diff, not filename alone.
6. Migrations require ordered compatibility analysis before any port.
7. Production/private configuration examples must not leak secrets or private endpoints into public artifacts.
8. No merge, force-push, rebase or release action is authorized by this inventory.

## Required next comparison slices

### Slice 1 — shared application core

Compare:

- `processual_kernel/`;
- public portions of `cgtlib/`;
- shared `processual_api/` modules;
- authentication;
- marketplace/billing/quota/pricing modules;
- migrations used by both distributions.

### Slice 2 — private-only boundary

Identify and preserve:

- `cgtlib/private/` or equivalent private packages;
- private connector/provider implementations;
- private deployment/runtime configuration;
- private tests that must never enter the public build.

### Slice 3 — build and packaging

Compare:

- `pyproject.toml`;
- Dockerfile;
- `.dockerignore`;
- workflows;
- package inclusion/exclusion;
- public private-module stripping rules;
- release/build scripts.

### Slice 4 — documentation/config templates

Classify drift in:

- `.env.example`;
- `.env.production.example`;
- deployment docs;
- operator/readiness docs;
- feature flag defaults.

### Slice 5 — tests and CI

Require evidence for:

- public full suite;
- private full suite;
- public exclusion of private packages/tests;
- shared migration compatibility;
- public and private image builds.

## Current qualification state

```text
PublicPrivateRepositoriesIdentified=True
ExactMainHeadsPinned=True
BlindSyncAllowed=False
TopLevelDriftConfirmed=True
RepositoryReconciliationQualified=False
MergePerformed=False
ProductionAuthorityGranted=False
```

## Immediate next task

Build a classified shared/private path inventory and then inspect exact semantic drift for the shared application core before proposing any file movement.
