# SETTINGS-SANDBOX-QUALIFICATION-01

## Purpose

Qualify the Settings sandbox API-key path end-to-end without granting production authority.

## Stage 1A — Current implementation inventory

Status: COMPLETE

Verified in repository code:

- Client self-service issuance is restricted to client-visible, read-only sandbox operational profiles.
- Self-service keys are marked `environment=sandbox`.
- `production_allowed=False` and `runtime_connector_approved=False` are preserved at issuance.
- Raw API-key material is returned only from create/rotate responses and the persisted legacy record contains a hash instead of the raw secret.
- Legacy dynamic verification denies revoked/disabled/expired records and marks time-expired records as expired.
- Legacy dynamic verification records last-use metadata and usage count for a valid key.
- The commercial runtime already contains PostgreSQL subscription runtime, quota-account, and immutable usage-ledger authority.

Qualification regression coverage exists in `tests/test_settings_sandbox_qualification_01.py` for the legacy security baseline.

## Stage 1B — Security baseline regression lock

Status: COMPLETE IN CODE / CI EXECUTION PENDING

Coverage added for:

- hash-only persisted key material;
- valid sandbox-key authentication and usage update;
- revoked-key denial;
- expired-key denial and durable expired status;
- no production/runtime connector authority in the persisted sandbox record.

The stacked PR does not currently trigger the repository's public CI because public CI is scoped to pull requests targeting `main`, while this qualification PR is intentionally stacked on the Admin Governance branch. Absence of a workflow run is therefore not evidence of pass or failure.

## Stage 1C — Durable quota authority selection

Status: COMPLETE

No new quota ledger was introduced. The qualification path will reuse the existing PostgreSQL commercial runtime:

- `admin_market_subscription_runtime`;
- `admin_market_subscription_quota_accounts`;
- `admin_market_subscription_usage_ledger`.

The existing usage service obtains row locks for runtime and quota authority, verifies active/grace subscription access, checks customer/quota-profile binding, applies the quota reservation, and writes an idempotent immutable usage-ledger row in the same unit of work.

## Stage 1D — Durable sandbox API-key authority

Status: IMPLEMENTED IN CODE / AUTH WIRING AND REAL DB PROOF PENDING

Added migration `20260818_0055_sandbox_api_key_authority.py` and PostgreSQL model/repository `processual_api/services/sandbox_api_key_persistence.py`.

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

Added `verify_durable_sandbox_api_key()` with fail-closed subscription-runtime checks. It grants an identity only when the key is enabled, unrevoked, unexpired, hash-valid, customer-bound to the subscription runtime, and the runtime is `active` or `grace`. Returned identity explicitly carries `production_allowed=False` and `runtime_connector_approved=False`.

Contract coverage was added in `tests/test_sandbox_api_key_authority_postgres_contract.py` for active runtime acceptance, suspended runtime denial, and expiration before runtime authority.

## Remaining blockers for SETTINGS-SANDBOX-QUALIFICATION-01

The qualification gate remains open because:

1. `get_current_user` is not yet wired to `verify_durable_sandbox_api_key()`; the live request path still reaches the legacy JSON verifier.
2. Settings/Admin issuance, rotation and revocation are not yet writing the durable PostgreSQL authority record.
3. The API-key request path is not yet connected to the existing PostgreSQL subscription usage service for metered operations.
4. Real PostgreSQL migration/CRUD/revocation/expiry evidence has not yet been executed in an isolated qualification environment.
5. Redis-backed coordination or an explicit proof that PostgreSQL row-locking alone is sufficient for the selected request topology remains to be qualified.
6. Parallel-request no-overshoot evidence is outstanding.
7. Qualification cleanup evidence is outstanding.
8. Browser/external-client E2E is outstanding.

## Mandatory next implementation slice

Wire durable sandbox authority into authentication and issuance, then use the existing PostgreSQL subscription usage authority for metered requests. After wiring, execute real PostgreSQL/Redis concurrency qualification rather than relying on unit mocks.

The resulting implementation must prove:

1. raw secret is never persisted;
2. client/owner, environment, plan, scopes, expiry, purpose and audit actor are durable;
3. revoked and expired keys fail immediately;
4. subscription state removes runtime authority;
5. entitlement denial occurs before consumption;
6. quota reservation/commit/release is atomic and idempotent;
7. parallel requests cannot exceed the quota;
8. sandbox authority cannot become production authority implicitly;
9. qualification data can be cleaned up deterministically.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

Reason: durable authority is now implemented as a code foundation, but the live auth/issuance path and real PostgreSQL/Redis E2E/concurrency evidence are not yet complete.
