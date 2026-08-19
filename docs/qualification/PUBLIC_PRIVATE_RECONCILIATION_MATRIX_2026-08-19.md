# Public / Private Repository Reconciliation Matrix — 2026-08-19

**Public repository:** `don-zak/processual-maestro-kernel`  
**Public main at review:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private repository:** `don-zak/processual-maestro-kernel-private`  
**Private main at review:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **RECONCILIATION IN PROGRESS — NO CROSS-REPOSITORY PORT APPLIED YET**

## Purpose

Classify repository drift before porting the latest approved public core into the private baseline. The goal is to preserve private-only integrations while preventing the private repository from silently freezing an older public core.

This record does not authorize merge, release, staging or production.

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

These demonstrate substantial shared ancestry/core.

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

The kernel reconciliation unit has now been semantically classified **READY TO PORT**.

Most kernel files/subtrees are byte-identical. Reviewed differences are shared-core modernization rather than private behavior, principally `str, Enum` → `StrEnum`, plus minor lint cleanup.

Confirmed COPY-CANDIDATE examples:

- `processual_kernel/audit.py`
- `processual_kernel/types.py`
- `processual_kernel/adaptive_types.py`
- `processual_kernel/notifications/types.py`
- `processual_kernel/security/envelopes.py`
- `processual_kernel/security/crypto.py`
- `processual_kernel/security/keyring.py`
- `processual_kernel/security/policies.py`
- `processual_kernel/adaptive/ops_governance.py`
- reviewed adaptive efficiency drift

Detailed record:

`docs/qualification/PUBLIC_PRIVATE_KERNEL_RECONCILIATION_UNIT_2026-08-19.md`

Private main remains unchanged.

## 3. `cgtlib` findings

Most CGT formal-core modules are shared exactly, but a genuine private-engine boundary exists.

### IDENTICAL examples

- `cgtlib/aftermath.py`
- `batch.py`
- `benchmark_surfaces.py`
- `catalogs.py`
- `comparative_envelopes.py`
- `compatibility.py`
- `constants.py`
- `errors.py`
- `evaluators.py`
- `reference_data.py`

### Shared-core COPY/MERGE candidates

- `cgtlib/api.py` — private still embeds the stable API tuple; public delegates it to `_stable_api.py` and exposes newer reference-data API.
- `cgtlib/_stable_api.py` — present in public, absent from private; should be added during private core port.
- `cgtlib/_fallback.py` — public imports stable API from dependency-light `_stable_api.py`; private still imports it through `api.py`.
- `cgtlib/__init__.py` — reconcile shared exports while preserving private-engine composition behavior.

### PRIVATE-PRESERVE

The genuine private boundary is:

- `cgtlib/private/`

including private compute/equation/calibration/threshold modules. It must remain private and absent from public builds.

### Corrected classification: `cgtlib/data/`

`cgtlib/data/` is **not private-only**. Both repositories contain identical `cgtlib/reference_data.py`, which requires `cgtlib.data/reference_scenarios.json` through `importlib.resources`.

Private contained the canonical non-secret resource package while public main did not. The public qualification branch has therefore restored:

- `cgtlib/data/__init__.py`
- `cgtlib/data/reference_scenarios.json`
- `tests/test_cgtlib_reference_data_packaging.py`

The data contains only canonical formal-core scenarios and is shared product material.

Detailed record:

`docs/qualification/PUBLIC_PRIVATE_CGTLIB_RECONCILIATION_UNIT_2026-08-19.md`

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

These must be checked against private product architecture. If private is intended to contain the complete public product plus private integrations, absence is drift and they become port candidates.

### PRIVATE-PRESERVE

Private contains private-only surfaces including:

- `processual_api/data/`
- `processual_api/private_integrations/`

These must not be introduced into the public repository and must not be deleted during private reconciliation unless deeper semantic review proves a path is actually shared product data, as happened with `cgtlib/data`.

## 5. Public-exclusion invariant

Reconciliation must preserve:

1. genuine private-only paths remain private;
2. public build/test/package output contains no private engine/integration modules;
3. shared public core can be ported into private without converting private-only code into public dependencies;
4. private entrypoints may compose private modules, but shared modules remain usable when private modules are absent.

## 6. Safe port order

Do not perform a repository-wide copy.

1. `processual_kernel` — classification complete, ready to port on a dedicated private branch.
2. `cgtlib` — port shared API/fallback contract while preserving `cgtlib/private/`; public package-data defect repaired on qualification branch.
3. reconcile `processual_api/auth` and `billing` against newer public contracts.
4. reconcile `processual_api/admin_marketplace`, readiness and execution surfaces into private if product parity requires them.
5. semantically merge `processual_api/integrations` and `main.py` around private-only registrations.
6. reconcile Alembic migrations and confirm one coherent private migration head.
7. reconcile CI/build/container configuration without removing private build requirements.
8. run private full suite plus public-exclusion checks.
9. build both public and private images.
10. retain exact drift/evidence report before declaring repository reconciliation closed.

## 7. Current decision

**Repository reconciliation is not yet closed.**

Unsafe strategies remain rejected:

- copying the entire public repository over private;
- preserving all private shared-core drift merely because it exists in the private repository.

The current execution unit is deep comparison of `processual_api/auth` and `processual_api/billing`.

## 8. Authority state

- no cross-repository code port performed;
- private `main` unchanged;
- no merge performed;
- no staging authority granted;
- no production authority granted;
- deferred real-environment proof backlog remains mandatory.