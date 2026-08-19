# Public / Private Repository Reconciliation Matrix — 2026-08-19

**Public repository:** `don-zak/processual-maestro-kernel`  
**Public main at review:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private repository:** `don-zak/processual-maestro-kernel-private`  
**Private main at review:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **RECONCILIATION IN PROGRESS — NO CROSS-REPOSITORY PORT APPLIED YET**

## Purpose

Classify repository drift before porting the latest approved public core into the private baseline. The goal is to preserve private-only integrations while preventing the private repository from silently freezing an older public core.

This record is read-only analysis of the two `main` branches. It does not authorize merge, release, staging or production.

## Classification vocabulary

- **COPY-CANDIDATE** — shared public-core path whose private equivalent should normally converge to the approved public version after focused tests.
- **MERGE-CANDIDATE** — shared path with private-specific behavior; requires semantic merge rather than overwrite.
- **PRIVATE-PRESERVE** — private-only material that must remain absent from public and must not be deleted during public-core porting.
- **PUBLIC-ONLY / REVIEW** — public functionality absent from the private top-level surface; determine whether it belongs in the private product baseline before porting.
- **IDENTICAL** — same blob/tree identity at the inspected boundary.

## 1. Root-level findings

### Identical examples

The root inventory shows exact shared blobs for several repository-control files, including examples such as:

- `.dockerignore`
- `.flake8`
- `.gitattributes`
- `.pre-commit-config.yaml`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `EXTERNAL_READINESS_REPORT.md`

These are evidence that the repositories still share a substantial common ancestry/core.

### MERGE-CANDIDATE root paths

The following root paths differ and must not be overwritten blindly:

- `.env.example`
- `.env.production.example`
- `.gitignore`
- `.github/`
- `DEPLOYMENT_EXTERNAL.md`
- `Dockerfile`

Reason: environment/runtime/build differences can encode private deployment behavior or newer public security/configuration contracts. Each requires semantic comparison.

## 2. `processual_kernel` findings

The inspected top-level kernel surface is mostly shared exactly.

### IDENTICAL inspected files

Examples with the same blob identity include:

- `processual_kernel/__init__.py`
- `adaptive_toolkit.py`
- `cgt_bridge.py`
- `continuity.py`
- `governor.py`
- `kernel.py`
- `observability/` subtree at the inspected boundary

### COPY/MERGE candidates

The following differ between public and private:

- `processual_kernel/adaptive_types.py`
- `processual_kernel/audit.py`
- `processual_kernel/types.py`
- `processual_kernel/adaptive/`
- `processual_kernel/notifications/`
- `processual_kernel/security/`

Default disposition: **COPY-CANDIDATE unless a private-only dependency or contract is found during semantic diff**.

These are core-kernel paths. Private drift here should be justified explicitly rather than preserved by default.

## 3. `cgtlib` findings

Most inspected CGT library modules are shared exactly, but the private repository also carries private-oriented surface differences.

### IDENTICAL examples

Examples include:

- `cgtlib/aftermath.py`
- `batch.py`
- `benchmark_surfaces.py`
- `catalogs.py`
- `comparative_envelopes.py`
- `compatibility.py`
- `constants.py`
- `errors.py`
- `evaluators.py`

### MERGE-CANDIDATE

The following inspected entrypoints differ:

- `cgtlib/__init__.py`
- `cgtlib/_fallback.py`
- `cgtlib/api.py`

These are not safe overwrite targets because entrypoints/fallbacks may intentionally expose private functionality when available.

### PRIVATE-PRESERVE

Private includes additional data/private material not present on the inspected public surface, including:

- `cgtlib/data/`

Any deeper private CGT subtree discovered during porting must remain excluded from public build outputs.

## 4. `processual_api` findings

This is the highest-risk reconciliation surface.

### IDENTICAL inspected boundary

- `processual_api/__init__.py`
- `processual_api/adapters/`
- `processual_api/cache/`

### Shared but divergent — MERGE/COPY review required

Private and public both contain, but with different tree/blob identities:

- `processual_api/auth/`
- `processual_api/billing/`
- `processual_api/cgt_governor/`
- `processual_api/db/`
- `processual_api/dependencies.py`
- `processual_api/integrations/`
- `processual_api/main.py`
- middleware/router/schema/service/static surfaces as discovered in deeper comparison

`processual_api/main.py` is especially high risk: the public and private file sizes differ substantially, so it must be semantically merged around router/runtime registration rather than copied.

### PUBLIC-ONLY / REVIEW at inspected top-level

Public exposes newer/expanded top-level surfaces including:

- `processual_api/admin_marketplace/`
- `processual_api/admin_audit_log.py`
- `processual_api/api_readiness.py`
- `processual_api/api_readiness_gate.py`
- `processual_api/execution/`

These must be checked against the private product architecture. If the private product is intended to contain the complete public product plus private integrations, absence is drift and they become port candidates.

### PRIVATE-PRESERVE

Private contains private-only surfaces including:

- `processual_api/data/`
- `processual_api/private_integrations/`

These must not be introduced into the public repository and must not be deleted during private reconciliation.

## 5. Public-exclusion invariant

The public build already documents/enforces the principle that private modules must remain excluded. Reconciliation must preserve this invariant:

1. private-only paths remain in the private repository;
2. public build/test/package output contains no private modules;
3. public shared core can be ported into private without converting private-only code into public dependencies;
4. private entrypoints may compose private modules, but shared modules must remain usable in the public build without them.

## 6. Safe port order

Do not perform a repository-wide copy.

Recommended order:

1. reconcile `processual_kernel` divergent shared-core files/subtrees;
2. reconcile safe shared `cgtlib` modules while preserving private entrypoints/data;
3. reconcile `processual_api/auth` and `billing` against the newer public contracts;
4. reconcile `processual_api/admin_marketplace`, readiness and execution surfaces into private if product parity requires them;
5. semantically merge `processual_api/integrations` and `main.py` around private-only registrations;
6. reconcile Alembic migrations and confirm one coherent private migration head;
7. reconcile CI/build/container configuration without removing private build requirements;
8. run private full suite plus public-exclusion checks;
9. build both public and private images;
10. retain exact drift/evidence report before declaring repository reconciliation closed.

## 7. Current decision

**Repository reconciliation is not yet closed.**

The evidence is sufficient to reject two unsafe strategies:

- copying the entire public repository over private;
- preserving all private shared-core drift merely because it is in the private repository.

The next execution unit is the focused semantic reconciliation of the divergent `processual_kernel` paths, followed by tests, before moving into `processual_api`.

## 8. Authority state

This reconciliation analysis does not change any runtime or release authority:

- no merge performed;
- no public/private cross-repository port performed yet;
- no staging authority granted;
- no production authority granted;
- deferred real-environment proof backlog remains mandatory.