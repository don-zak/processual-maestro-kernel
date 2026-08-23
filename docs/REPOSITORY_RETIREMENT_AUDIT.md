# Repository Retirement Audit

Status: Stage 1 legacy quota/usage retirement closed

DeletionAuthorized: false (repository-wide destructive cleanup remains unauthorized outside the completed candidate-specific retirement below)

This audit records evidence-backed retirement decisions. A file is not deleted merely because a newer implementation exists. DELETE requires runtime/import, test, migration/history, compatibility, real-database, and full-regression evidence.

## Current classification

| Candidate | Classification | Evidence | Required next proof |
| --- | --- | --- | --- |
| `processual_api/admin_marketplace/subscription_usage_service.py` | `DELETE_COMPLETED_QUALIFIED` | All production consumers were migrated to authoritative quota-cycle usage; the file is deleted; the retirement gate requires it to remain absent; full Public CI is green on the qualified retirement head. | None for this retired candidate. Do not restore without a new authority decision and migration contract. |
| Legacy `AdminMarketSubscriptionQuotaAccount` persistence | `SCHEMA_RETIREMENT_COMPLETED` | Alembic `20260822_0060` backfills and verifies legacy quota accounts into authoritative quota cycles before dropping `admin_market_subscription_quota_accounts`; real PostgreSQL Launch Closeout proof is green. ORM/repository/UoW exposure has been removed. | Keep migration-chain and real-DB retirement proof green. |
| Legacy `AdminMarketSubscriptionUsageLedger` persistence | `SCHEMA_RETIREMENT_COMPLETED` | Alembic `20260822_0060` preserves and verifies idempotency-bound usage history in quota-cycle usage before dropping `admin_market_subscription_usage_ledger`; ORM/repository/UoW exposure has been removed. | Keep migration-chain and real-DB retirement proof green. |
| `processual_api/admin_marketplace/subscription_quota_usage.py` | `KEEP_AUTHORITATIVE` | Production usage is quota-cycle authoritative and server-selects the current cycle. Real PostgreSQL replay/concurrency/quota enforcement gates are green. | Keep authoritative path green on all release heads. |
| `processual_api/admin_marketplace/subscription_usage_router.py` | `KEEP_AUTHORITATIVE_HTTP` | HTTP usage binds customer/subscription authority server-side and delegates to quota-cycle usage. | Keep HTTP authority path green on all release heads. |
| `processual_api/staging_smoke.py` | `KEEP_LAUNCH_GATE` | Requires quota-cycle usage, rejects installation of the retired quota-account service, and rejects client-selected quota cycles. | Keep this gate green on all release heads. |
| `processual_api/routers/client_provider_alias_18.py` | `KEEP_COMPATIBILITY_HOLD` | Separate compatibility hold; not part of the quota/usage retirement candidate. | Requalify independently before any destructive change. |
| `processual_api/routers/settings_provider_test_runtime.py` | `KEEP_ACTIVE_RUNTIME_WITH_DEPRECATED_COMPATIBILITY` | Separate active runtime compatibility hold. | Requalify independently before any destructive change. |
| `processual_api/services/plan_store.py` | `KEEP_ACTIVE_TRANSITIONAL_AUTHORITY_BRIDGE` | Separate authority bridge hold. | Requalify independently before any destructive change. |

## Qualified retirement implementation

The closed quota/usage retirement consists of one authoritative path:

1. Assessment, direct/catalog activation, runtime backfill, and sandbox usage were migrated away from legacy quota-account persistence.
2. `subscription_runtime_bootstrap.py` now delegates quota creation to authoritative quota-cycle bootstrap.
3. Alembic revision `20260822_0060_retire_legacy_subscription_quota.py` performs guarded legacy data backfill and verification before dropping the two legacy tables.
4. The old standalone `subscription_legacy_quota_cycle_backfill.py` utility was removed so Alembic is the single migration authority.
5. `subscription_usage_service.py` was removed.
6. Legacy ORM models and repositories were removed from `subscription_runtime_persistence.py` and from the Admin Marketplace unit of work.
7. `tests/test_legacy_subscription_usage_retirement_gate_a3.py` requires the retired runtime files to be absent and rejects production references to the retired service, repositories, and ORM models.
8. `tests/integration/test_legacy_quota_retirement_migration_postgres.py` proves the `0059 -> 0060` transition on real PostgreSQL, including history preservation and physical table retirement.

## Verified launch and retirement evidence

Qualified retirement HEAD:

`e2aefa982017dadc3ab3142fef31ed7f1651d364`

The following GitHub Actions gates completed successfully on that exact head:

- CI (Public) #1538 — SUCCESS
- Launch Closeout Gate #327 — SUCCESS
- Sandbox Integration Qualification #781 — SUCCESS
- Program Release Qualification #631 — SUCCESS
- Packaging Qualification #599 — SUCCESS
- Public Docker Build #473 — SUCCESS
- CAMARA Public Source Contracts #643 — SUCCESS
- Repository Evidence Closeout #184 — SUCCESS
- CI (Private monorepo) #1538 — SKIPPED as expected for the public qualification branch

The preceding Public CI failure was isolated to one stale test importing the intentionally retired usage repository. That test was converted into a retirement contract; on the qualified head the complete Public CI is green.

Launch Closeout Gate #327 exercises the guarded PostgreSQL retirement path: PostgreSQL is first migrated to revision `20260822_0059`, the retirement migration integration test advances it through `20260822_0060`, verifies preservation of authoritative quota/usage history and removal of the legacy tables, then the consolidated PostgreSQL/Redis authority suite runs at the new head.

## Retirement rule

Every destructive candidate must pass this sequence independently:

1. Static dependency/import search.
2. Production runtime route/service search.
3. Tests and compatibility-contract review.
4. Migration/schema/history review.
5. Real PostgreSQL/Redis proof where stateful behavior is involved.
6. Full repository regression.
7. Final candidate classification: `KEEP`, `ARCHIVE`, `DELETE_AUTHORIZED`, or `DELETE_COMPLETED_QUALIFIED`.

Candidate-specific qualification does not authorize deleting unrelated compatibility holds.

## Stage 1 closeout

1. **Real DB authority gate — PASS / CLOSED.**
2. **Legacy quota-account/usage retirement — PASS / CLOSED.** Historical state is guarded and migrated by `0060`; legacy runtime service, ORM repositories, and tables are retired.
3. **Zero-runtime-reference gate — PASS / CLOSED.** Production source is guarded against reintroducing retired quota/usage dependencies.
4. **Full Public CI / packaging / sandbox / release qualification — PASS / CLOSED on `e2aefa9...`.**
5. **Unrelated compatibility holds — KEEP.** Provider alias/runtime and `plan_store.py` remain independent holds and are not deletion-authorized by this retirement.

Stage 1 of the unified execution plan is therefore closed for the legacy quota/usage isolation and deletion scope. The next planned implementation stage is Agent Governance qualification, not additional destructive repository cleanup without new evidence.

## Authority boundary

Synthetic CI and qualification evidence do not grant Real Staging or production authority. Those gates remain governed by `docs/MASTER_REMAINING_EXECUTION_ROADMAP.md`.

Therefore:

`DeletionAuthorized=false` (repository-wide; unrelated KEEP holds remain protected)

`LegacyQuotaUsageRetirement=PASS_CLOSED`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`

`CommercialLaunch=NO_GO`
