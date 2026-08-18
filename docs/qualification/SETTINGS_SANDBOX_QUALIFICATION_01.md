# SETTINGS-SANDBOX-QUALIFICATION-01

## Purpose

Qualify the Settings sandbox API-key path end-to-end without granting production authority.

## Stage 1A — Current implementation inventory

Status: COMPLETE

Verified in repository code:

- Client self-service issuance is restricted to client-visible, read-only sandbox operational profiles.
- Self-service keys are marked `environment=sandbox`.
- `production_allowed=False` and `runtime_connector_approved=False` are preserved at issuance and authentication.
- Raw API-key material is returned only from create/rotate responses; durable persistence contains a one-way hash and non-secret prefix, never the raw secret.
- The commercial runtime already contains PostgreSQL subscription runtime, quota-account, and immutable usage-ledger authority.
- Admin evaluation grants are a separate subscription-independent authority and must not be represented as paid-subscription sandbox keys.

## Stage 1B — Security regression lock

Status: IMPLEMENTED / CURRENT QUALIFICATION RUN PENDING

Coverage now includes:

- hash-only persisted key material;
- valid durable sandbox-key authentication;
- revoked and expired durable-key denial;
- suspended-subscription denial;
- explicit fail-closed durable-match semantics;
- durable authority failure returning service-unavailable instead of falling through to legacy JSON;
- preservation of non-production authority.

The durable verifier uses three semantically distinct outcomes:

1. no matching durable secret: transition-compatible legacy evaluation may continue;
2. matching durable secret accepted: durable identity is authoritative;
3. matching durable secret denied: no legacy fallback is permitted.

Revoked/disabled/expired rows remain visible to prefix candidate lookup so a matching revoked secret cannot be misclassified as an authority miss.

## Stage 1C — Durable quota authority selection

Status: COMPLETE

No competing quota ledger was introduced. Durable sandbox keys reuse the existing PostgreSQL commercial runtime:

- `admin_market_subscription_runtime`;
- `admin_market_subscription_quota_accounts`;
- `admin_market_subscription_usage_ledger`.

The existing usage service obtains row locks for runtime and quota authority, verifies active/grace subscription access, checks customer/quota-profile binding, applies the quota reservation, and writes an idempotent immutable usage-ledger row in the same unit of work.

## Stage 1D — Durable sandbox API-key authority

Status: IMPLEMENTED / REAL POSTGRESQL LIFECYCLE PROOF ADDED, CI PENDING

Migration `20260818_0055_sandbox_api_key_authority.py` and PostgreSQL model/repository `processual_api/services/sandbox_api_key_persistence.py` provide the durable authority.

The durable record contains:

- hash and non-secret prefix only;
- client and owner binding;
- subscription and plan binding;
- operational profile and scopes;
- label, purpose, issued-to and issuing actor;
- mandatory `environment=sandbox` database constraint;
- enabled/revoked/expired/disabled state;
- expiry, revocation, last-use and usage metadata.

No raw secret column exists.

`verify_durable_sandbox_api_key()` grants an identity only when the presented secret matches a durable row, that row is enabled/unrevoked/unexpired, the customer matches the subscription runtime, and runtime access is `active` or `grace`.

`get_current_user()` now evaluates durable sandbox authority before the legacy verifier whenever durable mode is enabled. A durable denial returns 401; a durable database/runtime failure returns 503; neither condition may fall through to legacy authority.

The shared durable-mode policy is mandatory in production. `APP_ENV=production`, `ENVIRONMENT=production|prod`, or `settings.is_production=True` overrides an explicit `PMK_DURABLE_SANDBOX_API_KEYS=false`. Explicit disable remains a transition-only local/test option.

A real PostgreSQL lifecycle qualification test now exercises:

`issue -> authenticate -> rotate -> old secret denied -> new secret accepted -> revoke -> denied -> deterministic cleanup`

It also queries the durable row to prove the raw secret is not persisted. This test is present in the qualification workflow but is not counted as proof until the workflow completes successfully.

## Stage 1E — Durable Settings client provisioning

Status: IMPLEMENTED / CI PENDING

`/settings/client/api-keys` create/list/rotate/revoke routes now use durable PostgreSQL provisioning when durable mode is enabled.

Provisioning requires exactly one authoritative active subscription whose:

- customer matches the authenticated client;
- canonical plan code matches the eligible plan;
- runtime customer matches;
- runtime access stage is `active` or `grace`.

Write paths lock authoritative subscription/runtime state. The maximum-active-key check is performed inside the same transaction. Rotation revokes the old durable key and inserts the replacement in one transaction. The raw replacement secret is returned only once.

Legacy Settings JSON persistence remains available only as an explicit non-production transition path.

## Stage 1F — Durable usage and quota boundary

Status: IMPLEMENTED / REAL CONCURRENCY PROOF ADDED, CI PENDING

For identities authenticated as `session_type=sandbox_api_key`, `require_quota()` no longer calls the JSON `quota_store`.

Metered requests are sent to the existing subscription usage service using the authenticated subscription/customer/key identity. The request receives a bounded internal SHA-256 idempotency key. Free requests do not create usage ledger rows.

Failure posture:

- quota exhaustion -> HTTP 429 with `quota_source=subscription_usage_ledger`;
- subscription/runtime denial -> fail closed;
- database/usage authority failure -> HTTP 503;
- no durable-key quota failure can fall through to JSON quota state.

A real PostgreSQL concurrency test now creates an isolated quota of 5 units and launches 10 simultaneous one-unit reservations. The required proof is exactly 5 successes, 5 quota rejections, `used_units=5`, five immutable ledger rows totalling five units, followed by deterministic cleanup. The test is present in CI but is not counted as passed evidence until the workflow succeeds.

## Stage 1G — Qualification environment

Status: ACTIVE / LATEST RUN PENDING

`Sandbox Integration Qualification` runs against:

- PostgreSQL 17;
- Redis 7;
- Alembic head `20260818_0055`;
- no production credentials;
- no external provider credentials.

The runner repeatedly proved a clean Alembic upgrade to head after a PostgreSQL JSON compatibility defect was fixed in migration `20260807_0039`.

The workflow now includes focused lint/contracts for durable auth, provisioning, quota/usage, production durable-mode enforcement, endpoint discovery/provenance/path composition, and Integration Center UI contracts, plus the real PostgreSQL lifecycle and concurrency tests.

A previous run exposed a circular import caused by loading the Admin Marketplace runtime repository while `auth.security` was still initializing. The runtime repository import is now lazy inside the durable verifier while retaining an injection seam for focused tests. A newer qualification run must pass before this is accepted as closed evidence.

## Separate authority: admin evaluation grants

Status: NOT DURABLE / OUTSIDE COMMERCIAL SUBSCRIPTION AUTHORITY

`/settings/admin/evaluation-grants/{grant_id}/issue-key` issues subscription-independent pilot/evaluation keys with `subscription_required=False`. Its grant and key state still lives in Settings JSON and uses a separate evaluation-grant quota model.

This path must not be inserted into `sandbox_api_key_authority` by inventing a subscription because that table intentionally requires an authoritative subscription foreign key.

Therefore broad statements such as "all Settings/Admin API keys are durable" are not yet valid. Before full Settings sandbox qualification, the evaluation path needs one of two explicit outcomes:

1. a separate durable evaluation-grant/key/quota authority with equivalent revocation, expiry, atomic quota and concurrency proof; or
2. explicit exclusion/disablement of subscription-independent evaluation-key issuance in the environment being commercially qualified.

## Remaining blockers for SETTINGS-SANDBOX-QUALIFICATION-01

The gate remains open because:

1. the current qualification run must pass after the circular-import fix;
2. real PostgreSQL key lifecycle and parallel no-overshoot tests are written but not yet accepted as green CI evidence;
3. subscription-independent admin evaluation keys remain JSON-backed and require a separate durability decision;
4. legacy API-key fallback remains a controlled transition surface for durable no-match cases and requires an explicit production cutover/migration policy before legacy authority can be retired;
5. external-client/browser E2E and rendered Integration Center visual QA remain outstanding;
6. real provider/operator sandbox evidence remains outside this Settings key qualification and is required separately for external connector qualification.

## Mandatory acceptance conditions

The resulting implementation must prove:

1. raw secret is never persisted;
2. client/owner, environment, plan, scopes, expiry, purpose and audit actor are durable;
3. revoked and expired durable keys fail immediately;
4. subscription state removes runtime authority;
5. durable denial and authority failure cannot fall through to legacy state;
6. quota reservation is atomic and idempotent;
7. parallel requests cannot exceed quota;
8. sandbox authority cannot become production authority implicitly;
9. qualification data can be cleaned up deterministically;
10. every remaining non-durable API-key authority is explicitly migrated, excluded, or blocked before the broad qualification gate closes.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

Reason: the durable commercial sandbox chain is now wired in code and real PostgreSQL lifecycle/concurrency qualification tests have been added, but the latest CI evidence is still pending and the separate admin evaluation-key authority remains JSON-backed.