# Public / Private Admin Marketplace + Migration Reconciliation Unit — 2026-08-19

**Public main:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private main:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **MAJOR PARITY PREREQUISITE — PRIVATE MAIN UNCHANGED**

## Executive finding

The private repository does not contain the later shared Admin Marketplace package or the Alembic migration program required by the qualified public authentication/commercial architecture.

This makes both surfaces mandatory prerequisites for auth/billing parity. They are not optional feature additions.

## 1. Admin Marketplace absence in private

Public contains a substantial `processual_api/admin_marketplace/` package including authority, activation, persistence, commercial lifecycle, subscription, payment, secure webhook, reconciliation, quota/top-up and read-service components.

Private main returns no `processual_api/admin_marketplace/` path.

Public billing now imports Admin Marketplace services directly, including secure Lemon Squeezy webhook installation and subscription access resolution. Therefore public billing cannot be ported correctly into private until the required shared Admin Marketplace surface is present.

Disposition: **PUBLIC SHARED ADMIN MARKETPLACE PORT REQUIRED**.

This does not grant live commercial/payment authority. Live provider/deployed-browser/real-environment proof remains deferred under the program readiness backlog.

## 2. Alembic migration absence in private

Public contains an ordered Alembic migration chain beginning with identity/auth foundation and continuing through delivery, platform authority, account recovery, Admin Marketplace persistence and subsequent commercial/quota work.

Examples from the public chain include:

- `20260721_0001_identity_auth_foundation.py`
- `20260722_0002_identity_terms_acceptance.py`
- `20260722_0003_auth_delivery_outbox.py`
- `20260722_0004_auth_email_verification_lifecycle.py`
- `20260722_0005_auth_delivery_dispatcher.py`
- `20260722_0006_platform_authority.py`
- `20260723_0007_admin_recovery_email_supervisor_authority.py`
- `20260723_0008_recovery_email_verification_tokens.py`
- `20260723_0009_account_recovery_foundation.py`
- `20260723_0010_account_recovery_delivery_authority.py`
- `20260727_0011_admin_marketplace_persistence.py`
- later commercial/quota/subscription migrations.

Private main has no `alembic/` directory at all.

Disposition: **MIGRATION PROGRAM PORT REQUIRED** before the later public persistence-backed runtime can be considered private-parity capable.

## 3. Why code-only porting is prohibited

Porting auth/Admin Marketplace/billing modules without migrations would create an invalid private runtime where application code expects tables, constraints, indexes or lifecycle state that the private database cannot produce.

Likewise, inventing a new private-only schema instead of porting/reconciling the public migration history would create avoidable schema drift and complicate future upgrades/rollback.

Therefore reconciliation must preserve the public migration lineage unless a specific private-only migration conflict is proven and separately resolved.

## 4. Required migration qualification

After a controlled private branch receives the public migration chain, validate at minimum:

1. upgrade from the supported private baseline into the public shared schema;
2. exact Alembic head uniqueness;
3. downgrade/rollback behavior where supported by the public qualification contract;
4. public shared tables/constraints match expected models;
5. private-only data/integration tables remain preserved;
6. no public migration references private-only modules;
7. private application startup succeeds after migration;
8. auth recovery/delivery/Admin Marketplace/billing persistence tests pass;
9. backup/restore against the eventual real staging database remains a deferred real-environment proof.

## 5. Updated dependency order

The safe parity sequence is now:

1. shared `processual_kernel` port unit;
2. shared `cgtlib` contract/data unit while preserving `cgtlib/private`;
3. Alembic/shared database foundation;
4. full qualified public auth surface;
5. shared Admin Marketplace surface;
6. public billing/commercial/quota/pricing surface;
7. settings/middleware/router/main integration;
8. private-only integration compatibility;
9. full private tests/public-exclusion tests;
10. public/private image/package validation.

Depending on branch mechanics, steps 3–6 may need to land in one stacked parity branch because application modules and migrations are tightly coupled. They must still be reviewed as explicit sub-units.

## Current authority

- private `main` unchanged;
- no schema migration applied to any environment;
- no cross-repository code port performed;
- no merge performed;
- no staging/production authority granted;
- real-environment readiness proofs remain mandatory and deferred.