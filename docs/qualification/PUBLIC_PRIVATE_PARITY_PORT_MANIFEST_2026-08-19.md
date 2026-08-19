# Public / Private Parity Port Manifest — 2026-08-19

**Public source baseline:** `don-zak/processual-maestro-kernel@a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private target baseline:** `don-zak/processual-maestro-kernel-private@84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **PORT MANIFEST READY — PORT NOT APPLIED**

## Goal

Bring the private product baseline up to the later qualified public shared core while preserving genuine private CGT integrations and public-exclusion boundaries.

## Mandatory preservation set

These are private product boundaries and must survive reconciliation:

- `cgtlib/private/`
- `processual_api/private_integrations/`
  - `cgt17a/`
  - `cgt17b/`
  - `cgt17c/`
  - `cgt18/`
  - `cgt_bridge.py`
- private conditional composition of `routers.cgt17b_private` and `routers.cgt17c_private` when the private package is installed;
- private Docker/CI behavior that intentionally builds and validates the private target;
- sanitized private bridge/adapter boundaries that fail closed when private providers are absent or disabled.

No item in this preservation set may be copied into the public build.

## Port Unit P1 — `processual_kernel`

Status: **READY TO PORT**.

Public is the selected shared-core authority for the reviewed drift. Most differences are enum modernization and minor cleanup, not private behavior.

Source record:

`docs/qualification/PUBLIC_PRIVATE_KERNEL_RECONCILIATION_UNIT_2026-08-19.md`

Validation after application:

- focused kernel/adaptive/security tests;
- private full regression;
- no private imports introduced into shared kernel.

## Port Unit P2 — `cgtlib` shared formal core

Status: **PORT MANIFEST READY**.

Required actions:

- add public `cgtlib/_stable_api.py` to private;
- converge `cgtlib/api.py`;
- converge `cgtlib/_fallback.py`;
- reconcile shared exports in `cgtlib/__init__.py`;
- preserve `cgtlib/private/`;
- preserve/verify canonical `cgtlib/data/` resources.

Public qualification branch also repairs a discovered public packaging defect by restoring the shared canonical reference dataset package and regression coverage.

Source record:

`docs/qualification/PUBLIC_PRIVATE_CGTLIB_RECONCILIATION_UNIT_2026-08-19.md`

## Port Unit P3 — shared database / Alembic foundation

Status: **REQUIRED BEFORE PERSISTENCE-BACKED PARITY**.

Private currently has no Alembic directory while public has the later ordered identity/auth/commercial migration chain.

Port/reconcile the public migration lineage and validate one coherent private migration head before treating later auth/commercial persistence as available.

Source record:

`docs/qualification/PUBLIC_PRIVATE_ADMIN_MIGRATION_RECONCILIATION_UNIT_2026-08-19.md`

## Port Unit P4 — complete public authentication core

Status: **MAJOR PARITY PORT REQUIRED**.

Private auth is an older three-file surface. Public contains the qualified recovery, delivery, MFA, registration, session, platform authority and operational security program.

Required actions:

- port the complete public auth module set and tests;
- port associated migration/settings/middleware dependencies;
- reconcile callers of legacy `auth.router` / legacy `security.py` assumptions;
- do not retain an independent legacy authority path.

Source record:

`docs/qualification/PUBLIC_PRIVATE_AUTH_BILLING_RECONCILIATION_UNIT_2026-08-19.md`

## Port Unit P5 — shared Admin Marketplace

Status: **MAJOR PARITY PREREQUISITE**.

Private currently has no `processual_api/admin_marketplace/` package. Public billing depends directly on this surface.

Port the shared package and corresponding tests/migrations. Live payment-provider authority remains separately gated and is not granted by repository parity.

## Port Unit P6 — billing/commercial/quota/pricing core

Status: **MAJOR PARITY PORT REQUIRED**.

Private billing is an older monolithic router with direct provider calls and JSON-backed runtime state. Public has the later governed commercial authority, secure webhook/inbox/reconciliation, subscription, quota, top-up, billing statement and pricing architecture.

Required actions:

- port public billing and its shared commercial dependencies;
- retire or convert the legacy private router into a non-authoritative compatibility layer;
- prevent simultaneous JSON and governed persistence sources of truth;
- validate checkout/webhook/subscription/quota authority boundaries.

## Port Unit P7 — integration control plane

Status: **SEMANTIC MERGE REQUIRED**.

Public and private already share some exact integration contracts, including reviewed examples such as `adapter_contracts.py` and `connector_registry.py`.

Public contains a much larger later connector/enterprise qualification surface. Private contains a sanitized CGT adapter that calls the private provider fail-closed.

Required direction:

- use the later public integration control plane as shared base;
- preserve the private CGT adapter/bridge boundary;
- compare shared-but-different connector binding/credential/runtime contracts before replacement;
- retain private providers outside the public tree.

## Port Unit P8 — settings, middleware and application composition

Status: **SEMANTIC MERGE REQUIRED**.

Required direction:

- use later public settings/security configuration as base;
- use later public middleware set/order as base unless a documented private requirement exists;
- start `processual_api/main.py` from public composition;
- reintroduce private conditional router discovery/registration;
- verify private modules remain optional from the shared/public perspective;
- snapshot-test final private route inventory.

## Port Unit P9 — tests and public-exclusion contract

Required:

- port public tests that define shared product behavior;
- retain private CGT test suites;
- run the private full suite;
- run public-strip/public-boundary tests from the private repository;
- prove no `cgtlib/private` or `processual_api/private_integrations` material enters public packages/images;
- verify the public shared core works when private modules are absent.

## Port Unit P10 — build and CI reconciliation

Required:

- preserve the private Docker target and private-only validation workflows;
- converge shared dependency/build configuration where public is newer;
- retain private GHCR/package publication boundaries;
- build both public and private artifacts;
- run package/Twine validation;
- verify dependency/security/coverage gates;
- record exact source and artifact digests.

## Explicitly prohibited shortcut

Do not copy the entire public tree over private.

The private repository contains intentional confidential/private implementation paths and specialized CI/deployment behavior. Conversely, do not preserve every private shared-core file merely because it already exists there; large parts of private auth/billing/settings/runtime are demonstrably older than the qualified public core.

## Application order

Recommended stacked order:

```text
P1 kernel
→ P2 cgtlib shared core
→ P3 migrations/database
→ P4 auth
→ P5 Admin Marketplace
→ P6 billing/commercial/quota/pricing
→ P7 integration control plane
→ P8 settings/middleware/main composition
→ P9 tests/public exclusion
→ P10 build/CI/package validation
```

Tightly coupled units may share one dedicated private parity branch, but review/evidence should retain these unit boundaries.

## Current publication constraint

The current execution environment does not provide the authenticated local `gh` workflow required by the repository publication procedure for safe private branch creation/commit/push/draft-PR publication.

Therefore this manifest intentionally stops before mutating private `main` or fabricating a cross-repository publication path.

This is a tooling constraint, not evidence that parity is complete.

## Exit criteria for repository reconciliation

Repository reconciliation is closed only when:

- the port is applied to a dedicated private branch;
- shared-core differences are intentionally resolved;
- private-only boundaries are preserved;
- migrations reconcile to one valid head;
- public and private suites pass;
- public-exclusion tests pass;
- both package/image builds pass;
- exact drift evidence is retained;
- the result is reviewed without claiming real staging or production authority.

Until then:

`RepositoryReconciliationComplete=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
