# Public / Private Repository Reconciliation Matrix — 2026-08-19

**Public repository:** `don-zak/processual-maestro-kernel`  
**Public baseline inspected:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private repository:** `don-zak/processual-maestro-kernel-private`  
**Private baseline inspected:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **TRUST-BOUNDARY RECONCILIATION IN PROGRESS — NO REPOSITORY MIRRORING AUTHORIZED**

## Purpose

Classify repository drift while preserving an intentional trust boundary: the private repository is the proprietary mathematical execution environment, while the public repository owns governance, orchestration and public-safe contracts.

This matrix does not authorize merge, release, staging, production, whole-tree synchronization, or exposure of private source.

## Classification vocabulary

- **SHARED_PUBLIC_SAFE** — non-proprietary common code/data that may intentionally converge after focused semantic review and tests.
- **PRIVATE_PRESERVE** — proprietary/private implementation that must remain absent from public source, package, image, logs and evidence.
- **BOUNDARY_ADAPTER** — controlled mediation between public governance and private execution; public input is bounded/opaque and output is strictly sanitized.
- **ARCHITECTURAL_VIOLATION** — any path that mixes public governance with private implementation, discovers private modules from public code, performs protected math as a public fallback, or exposes prohibited intermediate/private data.
- **IDENTICAL** — same blob/tree identity at the inspected boundary; identity alone does not determine whether future changes remain shared-safe.

Historical labels such as `COPY-CANDIDATE`, `MERGE-CANDIDATE` and broad "parity" are superseded where they conflict with these classifications.

## 1. Root-level findings

Several repository-control files were identical at the inspected baselines, including examples such as `.dockerignore`, `.flake8`, `.gitattributes`, `.pre-commit-config.yaml`, `CHANGELOG.md`, `CONTRIBUTING.md`, and `EXTERNAL_READINESS_REPORT.md`.

Differences in `.env.example`, `.env.production.example`, `.gitignore`, `.github/`, `DEPLOYMENT_EXTERNAL.md`, and `Dockerfile` require semantic review. They are not automatically port candidates because build/deployment differences may encode the intentional private trust context.

## 2. `processual_kernel`

Most inspected kernel files/subtrees share common ancestry and many are byte-identical. Reviewed differences such as `Enum` modernization and lint cleanup may qualify as **SHARED_PUBLIC_SAFE**.

Previously reviewed examples include:

- `processual_kernel/audit.py`
- `processual_kernel/types.py`
- `processual_kernel/adaptive_types.py`
- `processual_kernel/notifications/types.py`
- `processual_kernel/security/envelopes.py`
- `processual_kernel/security/crypto.py`
- `processual_kernel/security/keyring.py`
- `processual_kernel/security/policies.py`
- `processual_kernel/adaptive/ops_governance.py`

Detailed record:

`docs/qualification/PUBLIC_PRIVATE_KERNEL_RECONCILIATION_UNIT_2026-08-19.md`

**Current classification:** reviewed common files may be `SHARED_PUBLIC_SAFE`; no unit-wide blind port is authorized. Any dependency on proprietary mathematical/provider state requires reclassification.

## 3. `cgtlib`

`cgtlib` is explicitly split by trust role; it is not one parity unit.

### `PRIVATE_PRESERVE`

- `cgtlib/private/`

This path contains the proprietary engine boundary and must remain private. It must not be copied into public source/artifacts or used as a public import dependency.

### `SHARED_PUBLIC_SAFE`

`cgtlib/data/` canonical reference resources were reviewed as non-secret product data. The public qualification branch restores:

- `cgtlib/data/__init__.py`
- `cgtlib/data/reference_scenarios.json`
- package-data declaration and regression coverage.

Shared API declarations/reference-data helpers may also qualify after file-level review.

### Resolved `ARCHITECTURAL_VIOLATION`

The public qualification branch discovered public `cgtlib` modules that imported `cgtlib.private` directly. Those public dependencies were removed. Public protected operations now use a fail-closed public surface rather than a proprietary fallback, and the public package explicitly reports `_HAS_PRIVATE=False`.

Mandatory continuing tests prove:

- public imports work with private modules absent;
- public wheels exclude `cgtlib/private/`;
- protected operations fail closed rather than reproduce protected math;
- canonical shared data remains available in the installed wheel.

Detailed record:

`docs/qualification/PUBLIC_PRIVATE_CGTLIB_RECONCILIATION_UNIT_2026-08-19.md`

## 4. `processual_api`

This remains the highest-risk reconciliation surface because public governance and historical CGT computation have been co-located.

### Public governance/security authority — generally `SHARED_PUBLIC_SAFE` or public-only authority

Examples:

- authentication/security governance;
- Admin Marketplace;
- billing/commercial/quota/pricing authority;
- database/persistence for public product state;
- integration admission/qualification/control plane;
- readiness and execution governance.

Absence of these modules from the private repository is **not automatically drift**. They should not be copied merely to make private resemble public. Private execution should consume only the governed references/contracts it actually requires.

### `PRIVATE_PRESERVE`

- `processual_api/private_integrations/`
- private mathematical/provider execution modules;
- private deployment-only composition that knows those modules.

These must remain absent from public artifacts.

### `BOUNDARY_ADAPTER`

The public qualification branch now contains a neutral `processual_api/integrations/private_evaluation_boundary.py` contract. It has no private implementation discovery and accepts only bounded opaque references. Its result is restricted to:

- `existence_rank`
- `dominant_constraint`
- `next_gate`
- `confidence_band`
- `explanation_code`
- `policy_version`

The private repository retains private-side adapter composition on Draft PR #49. Private provider knowledge belongs there, not in public code.

### `processual_api/main.py`

The prior recommendation to start private composition from public `main.py` and reinsert private routers is superseded.

Current rule:

- public app remains independently runnable with no source-level private discovery;
- private deployment may compose private modules only inside the private trust domain;
- protected public operations fail closed when private execution authority/provider is unavailable.

### Public CGT governor operational path

A legacy public governor path historically performed local score/vector/reward computation. Under the adopted trust-boundary architecture, that path cannot be an implicit substitute for private protected execution.

The qualification branch now makes legacy `govern_answer()` fail closed and adds `govern_sanitized_decision()` for public policy/repair orchestration from the approved sanitized decision contract. Further router/API migration away from raw score/vector responses remains an open reconciliation item.

Historical public heuristic/formal-core source is not automatically declared identical to proprietary private mathematics merely because mathematical terms overlap; classification must be evidence-based. However it is non-authoritative for private protected runtime execution.

## 5. Public-exclusion and non-leakage invariants

Reconciliation must preserve all of the following:

1. private-only source remains private;
2. public source/build/package/image contains no private implementation modules;
3. public runtime does not import, discover or introspect private modules;
4. public builds and tests work when private modules are absent;
5. protected evaluation fails closed if private execution is unavailable;
6. no private equation/weight/threshold/calibration/vector/intermediate state crosses the boundary;
7. provider exceptions are collapsed to generic public errors;
8. public logs/traces/telemetry/evidence do not retain private internals;
9. public auth/billing/commercial authority is not duplicated inside private merely for parity;
10. private implementation differences are intentional unless separately classified as shared/public-safe drift.

## 6. Current controlled reconciliation order

No repository-wide copy is permitted.

1. enforce source/package/runtime trust-boundary tests;
2. remove/isolate public runtime dependencies on private implementation;
3. qualify the neutral public boundary and private-side sanitized adapter;
4. migrate public operational governor/API paths away from raw vector/score contracts toward sanitized decisions;
5. reconcile only file-level `SHARED_PUBLIC_SAFE` kernel/formal-core drift;
6. keep public auth/Admin Marketplace/billing/quota/pricing as public authority unless deployment topology proves a private co-location requirement;
7. reconcile build/configuration separately for public and private trust contexts;
8. qualify public and private artifacts independently;
9. retain exact digest/evidence records without copying private source into public evidence.

## 7. Private Draft PR boundary status

Private branch `agent/private-public-trust-boundary-r1` and Draft PR #49 are dedicated to boundary qualification. They do not modify private mathematical formulas or grant runtime/staging/production authority.

The private adapter is explicitly private-side only, exposes the six-field sanitized result surface, and is being hardened so private provider exception details do not cross its boundary.

No merge is authorized by this matrix.

## 8. Current decision

**Repository reconciliation remains open.**

Rejected strategies include:

- copying public over private;
- copying private implementation into public;
- treating every public-only product module as missing private parity;
- conditional private-module imports from public runtime;
- local public protected-math fallback when the private provider is unavailable;
- returning raw private vectors/intermediate scores through public APIs or evidence.

Primary open runtime item: migrate remaining CGT governor/router/gateway surfaces that expose or rely on legacy raw score/vector contracts to the sanitized decision boundary without weakening public governance functions.

## 9. Authority state

`RepositoryReconciliationComplete=false`

`PrivateRuntimeAuthorityGranted=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`

No merge, staging mutation, production mutation, or real-environment proof is authorized by this record. Deferred real-environment proof remains mandatory.
