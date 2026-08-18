# SETTINGS-SANDBOX-QUALIFICATION-01

## Purpose

Qualify the Settings sandbox API-key path end-to-end without granting production authority.

## Stage 1A — Current implementation inventory

Status: COMPLETE

The repository now separates two non-production API-key authorities instead of forcing them into one model:

1. commercial subscription sandbox keys backed by `sandbox_api_key_authority` and the subscription usage ledger;
2. subscription-independent administrator evaluation grants backed by `evaluation_grant_authority`, `evaluation_api_key_authority`, and `evaluation_usage_ledger`.

Both paths preserve visible-once raw-key handling, hash-only durable persistence, explicit expiry/revocation, fail-closed authority errors, and `production_allowed=False`.

## Stage 1B — Commercial sandbox authentication boundary

Status: COMPLETE / POSTGRESQL-PROVEN

The commercial path remains qualified by run `#52` and subsequent regression runs:

- durable key authority is checked before legacy state;
- matching revoked/disabled/expired keys cannot fall through;
- suspended or mismatched subscription authority is denied;
- authority/database failure returns service-unavailable rather than weaker fallback;
- production cannot disable durable commercial sandbox authority;
- raw secrets are never persisted.

## Stage 1C — Commercial durable quota authority

Status: COMPLETE / POSTGRESQL-CONCURRENCY-PROVEN

Durable commercial sandbox identities use the existing subscription runtime and immutable usage ledger. `require_quota()` never sends `session_type=sandbox_api_key` identities to the JSON `quota_store`.

The real PostgreSQL concurrency proof reserves 10 simultaneous one-unit requests against a five-unit quota and requires exactly five successes, five rejections, `used_units=5`, and five ledger rows totaling five units.

## Stage 1D — Commercial durable key lifecycle

Status: COMPLETE / POSTGRESQL-PROVEN

Migration `20260818_0055_sandbox_api_key_authority.py` provides hash-only commercial sandbox key persistence bound to an authoritative subscription.

The real lifecycle proof is:

`issue -> authenticate -> rotate -> old denied -> new accepted -> revoke -> denied`

This table intentionally requires a subscription foreign key and is not reused for subscription-independent evaluation grants.

## Stage 1E — Durable administrator evaluation authority

Status: COMPLETE / POSTGRESQL-PROVEN

Migration `20260818_0056_evaluation_grant_authority.py` adds three independent authorities:

- `evaluation_grant_authority`;
- `evaluation_api_key_authority`;
- `evaluation_usage_ledger`.

No artificial subscription is created. The grant owns the quota and the evaluation keys reference the grant directly.

Database invariants include positive quota, non-negative usage/rejections, `used_requests <= max_requests`, constrained lifecycle states, unique key hashes, and idempotent usage ledger keys.

Run `#72` proved the clean Alembic chain through `20260818_0056` and verified all authority tables on PostgreSQL 17.

Run `#76` proved the durable evaluation lifecycle:

`create grant -> list -> issue three keys -> fourth key rejected -> raw secrets absent from persistence -> revoke grant -> all active keys revoked`

## Stage 1F — Evaluation production-mode and route boundary

Status: COMPLETE / CI-PROVEN

`evaluation_grant_mode.py` makes PostgreSQL durable authority the default when PostgreSQL is configured and forces durable evaluation authority in production even if `PMK_DURABLE_EVALUATION_AUTHORITY=false` is supplied.

Explicit legacy evaluation JSON mode remains a non-production transition mechanism only.

`/settings/admin/evaluation-grants` create/list/issue/revoke routes use the PostgreSQL authority whenever durable mode is enabled. Route boundary tests prove these durable paths do not read or write `evaluation_grants_v1` or Settings `api_keys` JSON state. Durable failures do not trigger JSON fallback.

## Stage 1G — Evaluation authentication and quota boundary

Status: COMPLETE / POSTGRESQL-CONCURRENCY-PROVEN / RUNTIME-WIRED

`get_current_user()` now evaluates API-key authority in this order:

1. durable commercial sandbox authority;
2. durable evaluation authority;
3. permitted non-production legacy transition authority.

A matching durable evaluation denial returns 401 and cannot fall through. Durable evaluation authority/database failure returns 503. When durable evaluation mode is enabled, a legacy identity claiming `entitlement_source=admin_evaluation_grant` is rejected instead of becoming a second evaluation source of truth.

Valid durable evaluation keys receive `session_type=evaluation_api_key`, grant/key authority identifiers, allowed scopes/tasks, `subscription_required=False`, and `quota_source=evaluation_usage_ledger`.

`require_quota()` routes `evaluation_api_key` identities only to `evaluation_usage_ledger`:

- free requests do not create usage rows;
- bounded SHA-256 request idempotency is used;
- quota exhaustion returns 429 with `quota_source=evaluation_usage_ledger`;
- inactive grant/key or subject/task mismatch fails closed;
- authority failure returns 503;
- no evaluation-key quota path falls through to JSON `quota_store`.

Run `#89` proved service-level authentication and real PostgreSQL quota concurrency. Ten simultaneous one-unit reservations against `max_requests=5` produced exactly five successes and five quota rejections, `used_requests=5`, `rejected_requests=5`, and five ledger rows totaling five units. Duplicate idempotency did not recharge quota.

Run `#95` proved the full runtime wiring and regression slice. Run `#96` repeated the green runtime slice while recording `evaluation_authority_runtime_wired=true` and `evaluation_authority_concurrency_proven=true` in the uploaded qualification evidence.

## Stage 1H — Production legacy dynamic API-key cutover

Status: COMPLETE / CI-PROVEN / FAIL-CLOSED

The remaining Settings-JSON dynamic API-key authority is now explicitly transition-only.

`legacy_api_key_mode.py` defines the cutover policy:

- `APP_ENV=production`, `ENVIRONMENT=production|prod`, or `settings.is_production=True` permanently disables Settings-JSON dynamic API-key authority;
- `PMK_LEGACY_DYNAMIC_API_KEYS=true` cannot reopen legacy authority in production;
- non-production environments may retain the legacy authority during migration and may explicitly disable it with `PMK_LEGACY_DYNAMIC_API_KEYS=false`.

The policy is enforced inside `api_key_store.verify_dynamic_api_key()` itself, before any `settings_*.json` scan, hash verification, usage mutation, or identity construction. This prevents another internal caller from bypassing the authentication boundary and resurrecting an obsolete credential.

The production cutover deliberately does not delete or rewrite old Settings JSON credentials automatically. Existing legacy records may remain on disk as inert historical state; they cannot authenticate in production and their usage metadata is not mutated by a rejected production attempt.

Run `#103` proved the cutover end-to-end:

- a real hash-only legacy dynamic key remains usable in the explicit non-production transition path;
- the same valid key is rejected with 401 in production even when `PMK_LEGACY_DYNAMIC_API_KEYS=true` requests enablement;
- the rejected production attempt leaves `usage_count=0` and `last_used_at=None`;
- a direct call to `verify_dynamic_api_key()` is also fail-closed in production;
- the focused commercial/evaluation/endpoint/UI regression slice remains green;
- the uploaded evidence records `legacy_dynamic_api_key_production_cutover=true`.

## Stage 1I — Qualification environment

Status: GREEN FOR DURABLE API-KEY AUTHORITY AND PRODUCTION CUTOVER

The current qualification workflow uses:

- PostgreSQL 17;
- Redis 7;
- Alembic head `20260818_0056`;
- no production credentials;
- no external provider credentials;
- no external network proof.

Important successful runs:

- `#52`: commercial sandbox lifecycle/quota foundation;
- `#61`: endpoint discovery hardening;
- `#68`: server-owned source-identity attestation;
- `#72`: evaluation authority schema/migration;
- `#76`: evaluation lifecycle;
- `#89`: evaluation auth service + no-overshoot concurrency;
- `#95`: evaluation HTTP/auth/quota runtime wiring and focused regression suite;
- `#96`: runtime-wired/concurrency evidence artifact confirmation;
- `#103`: production legacy dynamic API-key cutover and regression proof.

## External integration and UI qualification

Status: OPEN

These remain separate from durable Settings API-key persistence and production cutover:

- trusted acquisition/provider-authenticity verification for external API descriptions;
- pinned real provider/operator sandbox releases and credentials;
- CAMARA/TM Forum provider-specific qualification;
- external-client/browser E2E;
- rendered Integration Center visual QA.

Static Integration Center contracts are present, but rendered browser qualification has not been claimed.

## Remaining blockers for SETTINGS-SANDBOX-QUALIFICATION-01

The internal API-key authority blockers are closed for the qualified production policy: commercial sandbox keys are durable, administrator evaluation keys are durable, and Settings-JSON dynamic credentials are non-authoritative in production.

The umbrella gate remains open because:

1. external-client/browser E2E and rendered Integration Center visual QA remain outstanding;
2. trusted provider-source acquisition and real provider/operator sandbox evidence remain required for the external-integration portions of the umbrella release qualification.

## Mandatory acceptance conditions

Now proven by focused qualification:

1. raw commercial and evaluation secrets are never persisted;
2. commercial keys are bound to authoritative subscription/runtime state;
3. evaluation keys are bound to independent durable grants without fabricated subscriptions;
4. revoked/expired durable keys fail immediately;
5. durable denial and authority failure cannot fall through to weaker evaluation state;
6. commercial and evaluation quota reservations use durable idempotent ledgers;
7. parallel requests cannot exceed either tested quota authority;
8. production cannot disable either durable authority through transition flags;
9. evaluation route/auth/quota runtime wiring does not use Settings JSON in durable mode;
10. legacy Settings-JSON dynamic keys cannot authenticate or mutate usage state in production;
11. the legacy-enable flag cannot override the production cutover;
12. sandbox/evaluation authority cannot become production authority implicitly.

Still required before the broad Settings umbrella gate closes:

13. complete external-client/browser qualification evidence;
14. complete trusted external-source/provider sandbox qualification where the umbrella release depends on those integrations.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

Reason: the internal API-key authority chain and production legacy cutover now have green focused evidence, but the broad Settings release gate still includes external/browser qualification that has not been executed. No production authority is claimed by the qualification runner.
