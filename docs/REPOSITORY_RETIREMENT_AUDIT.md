# Repository Retirement Audit

Status: qualification in progress

DeletionAuthorized: false

This audit records evidence-backed retirement decisions. A file is not deleted merely because a newer implementation exists. DELETE requires runtime/import, test, migration/history, compatibility, real-environment, and full-regression evidence.

## Current classification

| Candidate | Classification | Evidence | Required next proof |
| --- | --- | --- | --- |
| `processual_api/admin_marketplace/subscription_usage_service.py` | `KEEP_ACTIVE_TRANSITIONAL_ASSESSMENT_BOOTSTRAP_HOLD` | The production HTTP usage router now calls `record_subscription_quota_usage_factory`, but the assessment subscription activation path still bootstraps the legacy quota-account persistence and its qualification test still consumes that exact assessment quota through `record_subscription_usage_factory`. | Migrate assessment/bootstrap persistence to authoritative quota-cycle creation and prove equivalent quota enforcement before any archive/delete decision. |
| `AdminMarketSubscriptionQuotaAccount` in `subscription_runtime_persistence.py` | `KEEP_ACTIVE_TRANSITIONAL` | `subscription_runtime_bootstrap.py` still constructs quota-account rows for active subscription bootstrap and replay validation, including assessment activation. | Replace bootstrap persistence with authoritative quota-cycle creation before considering retirement. |
| `AdminMarketSubscriptionUsageLedger` in `subscription_runtime_persistence.py` | `KEEP_ACTIVE_TRANSITIONAL` | The legacy usage service remains required by the assessment/bootstrap compatibility path even though the current HTTP usage router no longer installs it. | Remove the assessment/bootstrap dependency first; then migration/history and full-suite proof. |
| `processual_api/admin_marketplace/subscription_quota_usage.py` | `KEEP_AUTHORITATIVE` | Current production usage router calls this service and leaves `quota_cycle_id=None` so the server selects the current cycle. Real PostgreSQL replay and quota usage qualification are green. | Full repository regression on the final closeout HEAD. |
| `processual_api/admin_marketplace/subscription_usage_router.py` | `KEEP_AUTHORITATIVE_HTTP` | Current HTTP path binds customer identity server-side and delegates to quota-cycle usage. Endpoint tests were updated to the current quota-cycle command contract. | Full repository regression on the final closeout HEAD. |
| `processual_api/staging_smoke.py` | `KEEP_LAUNCH_GATE` | Requires quota-cycle usage, rejects installation of the legacy quota-account service on the HTTP path, and rejects client-selected quota cycles. | Keep this gate green on final HEAD. |

## Verified launch evidence

On closeout HEAD `c9b52c2294ae08de65b1348d1a90f1e102f63814`, the following GitHub Actions gates completed successfully:

- Launch Closeout Gate
- Sandbox Integration Qualification
- Program Release Qualification
- Packaging Qualification
- Public Docker Build
- CAMARA Public Source Contracts
- Repository Evidence Closeout

The Public CI job reached full pytest only after Ruff, flake8, mypy, Redis verification, private-module stripping, and capacity regression tests completed successfully.

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

1. **Real DB authority gate — PASS** — Alembic head on PostgreSQL plus Lemon checkout, quota usage, account recovery, webhook ingestion, and reconciliation against PostgreSQL/Redis are green in Launch Closeout Gate.
2. **Retirement qualification — IN PROGRESS** — dependency/history classification continues; assessment/bootstrap keeps the legacy quota-account path active, so no destructive cleanup is authorized.
3. **Final repository closeout — IN PROGRESS** — full Public CI pytest must be green after stale contract updates, followed by final coverage/security/public-private reconciliation review.

## Current blockers to deletion

- Assessment subscription activation still depends on `bootstrap_subscription_runtime_in_unit(...)`, which constructs the legacy quota-account persistence.
- Assessment quota enforcement still has an active qualification path through `record_subscription_usage_factory`.
- Full repository pytest is still running / must be green on the final closeout HEAD after contract-drift fixes.
- A data/schema migration proving safe retirement of historical quota-account and usage-ledger rows has not been completed.

Therefore:

`DeletionAuthorized=false`
