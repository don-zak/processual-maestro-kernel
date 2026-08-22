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
| `processual_api/admin_marketplace/subscription_quota_usage.py` | `KEEP_AUTHORITATIVE` | Current production usage router calls this service and leaves `quota_cycle_id=None` so the server selects the current cycle. Real PostgreSQL replay and quota usage qualification are green. | Keep the authoritative path green while the assessment/bootstrap bridge remains quarantined. |
| `processual_api/admin_marketplace/subscription_usage_router.py` | `KEEP_AUTHORITATIVE_HTTP` | Current HTTP path binds customer identity server-side and delegates to quota-cycle usage. Endpoint tests use the current quota-cycle command contract. | Keep the HTTP authority path green on all release heads. |
| `processual_api/staging_smoke.py` | `KEEP_LAUNCH_GATE` | Requires quota-cycle usage, rejects installation of the legacy quota-account service on the HTTP path, and rejects client-selected quota cycles. | Keep this gate green on all release heads. |

## Verified launch evidence

On final closeout HEAD `5bf92fd2245804f4b4e39cf78c430724e7ae52b3`, the following GitHub Actions gates completed successfully:

- CI (Public) #1426 — SUCCESS
- Launch Closeout Gate #103 — SUCCESS
- Sandbox Integration Qualification #669 — SUCCESS
- Program Release Qualification #486 — SUCCESS
- Packaging Qualification #486 — SUCCESS
- Public Docker Build #361 — SUCCESS
- CAMARA Public Source Contracts #531 — SUCCESS
- Repository Evidence Closeout #72 — SUCCESS

CI (Public) #1426 completed the complete `lint-and-test (3.14)` job successfully, including:

- public/private stripping verification;
- Redis verification;
- Ruff;
- flake8;
- mypy;
- capacity regression tests;
- full unit/full repository pytest;
- package build;
- package metadata validation.

The pytest failure-log upload step was skipped because the unit-test step succeeded.

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

The launch/repository closeout is now:

1. **Real DB authority gate — PASS / CLOSED** — Alembic head on PostgreSQL plus Lemon checkout, quota usage, account recovery, webhook ingestion, and reconciliation against PostgreSQL/Redis are green in Launch Closeout Gate.
2. **Retirement qualification — IN PROGRESS / KEEP HOLDS** — assessment/bootstrap still depends on the legacy quota-account path, so destructive cleanup remains unauthorized.
3. **Final repository closeout — PASS / CLOSED FOR PUBLIC CI** — the full Public CI job is green on `5bf92fd2245804f4b4e39cf78c430724e7ae52b3`, including full pytest and package validation.

## Current blockers to deletion

- Assessment subscription activation still depends on `bootstrap_subscription_runtime_in_unit(...)`, which constructs legacy quota-account persistence.
- Assessment quota enforcement still has an active qualification path through `record_subscription_usage_factory`.
- A data/schema migration proving safe retirement of historical quota-account and usage-ledger rows has not been completed.
- Public CI success does not itself authorize deleting an active compatibility/assessment path.

## Authority boundary

Synthetic CI and qualification evidence do not grant Real Staging or production authority. Those gates remain governed by `docs/MASTER_REMAINING_EXECUTION_ROADMAP.md`.

Therefore:

`DeletionAuthorized=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
