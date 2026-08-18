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

Status: COMPLETE FOR THE COMMERCIAL SUBSCRIPTION SANDBOX PATH

Green qualification evidence from `Sandbox Integration Qualification` run `#52` covers:

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

Status: COMPLETE FOR THE COMMERCIAL SUBSCRIPTION SANDBOX PATH

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

`get_current_user()` evaluates durable sandbox authority before the legacy verifier whenever durable mode is enabled. A durable denial returns 401; a durable database/runtime failure returns 503; neither condition may fall through to legacy authority.

The shared durable-mode policy is mandatory in production. `APP_ENV=production`, `ENVIRONMENT=production|prod`, or `settings.is_production=True` overrides an explicit `PMK_DURABLE_SANDBOX_API_KEYS=false`. Explicit disable remains a transition-only local/test option.

Run `#52` executed the real PostgreSQL lifecycle:

`issue -> authenticate -> rotate -> old secret denied -> new secret accepted -> revoke -> denied -> deterministic cleanup`

The test also queried the durable row and proved the raw secret was not persisted.

## Stage 1E — Durable Settings client provisioning

Status: COMPLETE FOR THE COMMERCIAL SUBSCRIPTION SANDBOX PATH

`/settings/client/api-keys` create/list/rotate/revoke routes use durable PostgreSQL provisioning when durable mode is enabled.

Provisioning requires exactly one authoritative active subscription whose:

- customer matches the authenticated client;
- canonical plan code matches the eligible plan;
- runtime customer matches;
- runtime access stage is `active` or `grace`.

Write paths lock authoritative subscription/runtime state. The maximum-active-key check is performed inside the same transaction. Rotation revokes the old durable key and inserts the replacement in one transaction. The raw replacement secret is returned only once.

Legacy Settings JSON persistence remains available only as an explicit non-production transition path.

## Stage 1F — Durable usage and quota boundary

Status: COMPLETE FOR THE COMMERCIAL SUBSCRIPTION SANDBOX PATH

For identities authenticated as `session_type=sandbox_api_key`, `require_quota()` no longer calls the JSON `quota_store`.

Metered requests are sent to the existing subscription usage service using the authenticated subscription/customer/key identity. The request receives a bounded internal SHA-256 idempotency key. Free requests do not create usage-ledger rows.

Failure posture:

- quota exhaustion -> HTTP 429 with `quota_source=subscription_usage_ledger`;
- subscription/runtime denial -> fail closed;
- database/usage authority failure -> HTTP 503;
- no durable-key quota failure can fall through to JSON quota state.

Run `#52` executed a real PostgreSQL concurrency proof with an isolated quota of 5 units and 10 simultaneous one-unit reservations. The test passed only after proving exactly 5 successes, 5 quota rejections, `used_units=5`, five immutable ledger rows totalling five units, followed by deterministic cleanup.

## Stage 1G — Qualification environment

Status: GREEN FOR THE FOCUSED COMMERCIAL SANDBOX SUITE

`Sandbox Integration Qualification` run `#52` completed successfully against:

- PostgreSQL 17;
- Redis 7;
- Alembic head `20260818_0055`;
- no production credentials;
- no external provider credentials.

The run passed service connectivity, a clean Alembic upgrade to head, direct verification of the durable sandbox authority migration, focused Ruff checks, the focused pytest qualification suite, evidence recording, artifact upload, and cleanup.

The workflow covers durable auth, provisioning, quota/usage, production durable-mode enforcement, endpoint discovery/provenance/path composition, Integration Center UI contracts, real PostgreSQL key lifecycle, and real PostgreSQL parallel quota/no-overshoot behavior.

A prior circular import exposed by CI was closed by lazily loading the Admin Marketplace runtime repository from the durable verifier while retaining a test injection seam. Run `#52` passed after this fix.

## Separate authority: admin evaluation grants

Status: NOT DURABLE / OUTSIDE COMMERCIAL SUBSCRIPTION AUTHORITY

`/settings/admin/evaluation-grants/{grant_id}/issue-key` issues subscription-independent pilot/evaluation keys with `subscription_required=False`. Its grant and key state still lives in Settings JSON and uses a separate evaluation-grant quota model.

This path must not be inserted into `sandbox_api_key_authority` by inventing a subscription because that table intentionally requires an authoritative subscription foreign key.

Therefore broad statements such as "all Settings/Admin API keys are durable" are not yet valid. Before full Settings sandbox qualification, the evaluation path needs one of two explicit outcomes:

1. a separate durable evaluation-grant/key/quota authority with equivalent revocation, expiry, atomic quota and concurrency proof; or
2. explicit exclusion/disablement of subscription-independent evaluation-key issuance in the environment being commercially qualified.

## Remaining blockers for SETTINGS-SANDBOX-QUALIFICATION-01

The focused commercial subscription sandbox chain now has green PostgreSQL qualification evidence. The umbrella gate remains open because:

1. subscription-independent admin evaluation keys remain JSON-backed and require a separate durability decision;
2. legacy API-key fallback remains a controlled transition surface for durable no-match cases and requires an explicit production cutover/migration policy before legacy authority can be retired;
3. external-client/browser E2E and rendered Integration Center visual QA remain outstanding;
4. real provider/operator sandbox evidence remains outside this Settings key qualification and is required separately for external connector qualification.

## Mandatory acceptance conditions

For the commercial subscription sandbox path, run `#52` now proves:

1. raw secret is never persisted;
2. client/owner, environment, plan, scopes, expiry, purpose and issuing actor are durable;
3. revoked and expired durable keys fail immediately;
4. subscription state removes runtime authority;
5. durable denial and authority failure cannot fall through to legacy state;
6. quota reservation is atomic and idempotent;
7. parallel requests cannot exceed quota;
8. sandbox authority cannot become production authority implicitly;
9. qualification data is cleaned up deterministically.

The remaining umbrella condition is:

10. every remaining non-durable API-key authority must be explicitly migrated, excluded, or blocked before the broad Settings sandbox gate closes.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

Reason: the commercial subscription sandbox key chain has green focused PostgreSQL qualification evidence, but the separate admin evaluation-key authority remains JSON-backed and the legacy no-match production cutover policy is not yet closed.