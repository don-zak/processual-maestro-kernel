# SETTINGS-SANDBOX-QUALIFICATION-01

## Purpose

Qualify the Settings sandbox API-key path end-to-end without granting production authority.

## Stage 1A — Current implementation inventory

Status: PARTIAL / NOT QUALIFIED FOR RELEASE

Verified in repository code:

- Client self-service issuance is restricted to client-visible, read-only sandbox operational profiles.
- Self-service keys are marked `environment=sandbox`.
- `production_allowed=False` and `runtime_connector_approved=False` are preserved at issuance.
- Raw API-key material is returned only from create/rotate responses and the persisted record contains a hash instead of the raw secret.
- Dynamic verification denies revoked/disabled/expired records and marks time-expired records as expired.
- Dynamic verification records last-use metadata and usage count for a valid key.
- Quota enforcement resolves plan authority and entitlement capability before charging a metered operation.

Qualification regression coverage added in `tests/test_settings_sandbox_qualification_01.py` for:

- hash-only persisted key material;
- valid sandbox-key authentication and usage update;
- revoked-key denial;
- expired-key denial and durable expired status;
- no production/runtime connector authority in the persisted sandbox record.

## Blocking finding — persistence and quota atomicity

The current dynamic API-key verifier and quota store still use `processual_api/data/settings_*.json` as their authoritative mutable backend.

This means SETTINGS-SANDBOX-QUALIFICATION-01 must remain open because the required production-like proof is not yet satisfied:

- no PostgreSQL-backed API-key authority has been proven for this path;
- no Redis-backed atomic quota reservation/consumption has been proven;
- file read/modify/write quota updates cannot be accepted as concurrency-safe proof;
- parallel-request prevention of quota overshoot is therefore not qualified;
- PostgreSQL/Redis cleanup and isolated qualification evidence remain outstanding.

## Mandatory next implementation slice

Replace the qualification path's JSON mutation authority with a durable PostgreSQL API-key record plus an atomic quota authority suitable for concurrent requests. Redis may be used for reservation/coordination only if PostgreSQL remains the durable reconciliation authority.

The resulting implementation must prove:

1. raw secret is never persisted;
2. client/owner, environment, plan, scopes, expiry, purpose and audit actor are durable;
3. revoked and expired keys fail immediately;
4. subscription state can remove runtime authority;
5. entitlement denial occurs before consumption;
6. quota reservation/commit/release is atomic and idempotent;
7. parallel requests cannot exceed the quota;
8. sandbox authority cannot become production authority implicitly;
9. qualification data can be cleaned up deterministically.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

Reason: security baseline exists, but real PostgreSQL/Redis runtime and concurrency evidence are not yet complete.
