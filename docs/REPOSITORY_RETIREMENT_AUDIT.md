# Repository Retirement Audit

Status: qualification in progress

DeletionAuthorized: false

This audit records evidence-backed retirement decisions. A file is not deleted merely because a newer implementation exists. DELETE requires runtime/import, test, migration/history, compatibility, real-environment, and full-regression evidence.

## Current classification

| Candidate | Classification | Evidence | Required next proof |
| --- | --- | --- | --- |
| `processual_api/admin_marketplace/subscription_usage_service.py` | `ARCHIVE_CANDIDATE_COMPAT_TEST_HOLD` | The production usage router now calls `record_subscription_quota_usage_factory`; staging smoke explicitly rejects installation of `record_subscription_usage_factory`. Legacy tests still import and exercise the old service. | Migrate or retire compatibility tests, run full suite, confirm no dynamic/runtime imports, then reclassify to ARCHIVE or DELETE. |
| `AdminMarketSubscriptionQuotaAccount` in `subscription_runtime_persistence.py` | `KEEP_ACTIVE_TRANSITIONAL` | `subscription_runtime_bootstrap.py` still constructs quota-account rows for active subscription bootstrap and replay validation. | Replace bootstrap persistence with authoritative quota-cycle creation before considering retirement. |
| `AdminMarketSubscriptionUsageLedger` in `subscription_runtime_persistence.py` | `KEEP_COMPATIBILITY_WITH_LEGACY_SERVICE` | The legacy usage service returns/writes this model and compatibility tests still exercise that path. | Remove legacy service dependency first; then migration/history and full-suite proof. |
| `processual_api/admin_marketplace/subscription_quota_usage.py` | `KEEP_AUTHORITATIVE` | Current production usage router calls this service and leaves `quota_cycle_id=None` so the server selects the current cycle. | Real PostgreSQL gate and full repository regression. |
| `processual_api/admin_marketplace/subscription_usage_router.py` | `KEEP_AUTHORITATIVE_HTTP` | Current HTTP path binds customer identity server-side and delegates to quota-cycle usage. | Real PostgreSQL gate and staging smoke. |
| `processual_api/staging_smoke.py` | `KEEP_LAUNCH_GATE` | Updated to require quota-cycle usage, reject the legacy quota-account service, and reject client-selected quota cycles. | CI execution on final HEAD. |

## Retirement rule

Every candidate must pass this sequence before destructive cleanup:

1. Static dependency/import search.
2. Production runtime route/service search.
3. Tests and compatibility-contract review.
4. Migration/schema/history review.
5. Real PostgreSQL/Redis proof where stateful behavior is involved.
6. Full repository regression.
7. Final classification: `KEEP`, `ARCHIVE`, or `DELETE_AUTHORIZED`.

## Immediate closeout order

The remaining launch/repository work is intentionally compressed into three stages:

1. **Real DB authority gate** — Alembic head on PostgreSQL plus Lemon checkout, quota usage, account recovery, webhook ingestion, and reconciliation against PostgreSQL/Redis.
2. **Retirement qualification** — finish dependency/history classification and eliminate stale compatibility references; no deletion while `DeletionAuthorized=false`.
3. **Final repository closeout** — full suite, coverage, static/security gates, public/private reconciliation, then CI review and the deletion decision.

## Current blockers to deletion

- Real PostgreSQL/Redis launch gate has not yet produced green CI evidence on the current HEAD.
- Legacy quota-account persistence is still used by subscription bootstrap.
- Legacy usage-service compatibility tests still exist.
- Full repository regression has not yet been rerun after retirement-gate changes.

Therefore:

`DeletionAuthorized=false`
