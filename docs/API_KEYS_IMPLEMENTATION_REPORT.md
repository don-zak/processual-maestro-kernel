# KEY-01 Implementation Report — Dynamic API Keys

## Processual Maestro Kernel v2.0.0

## Objective

The goal of KEY-01 was to connect dynamically generated API keys from the Settings interface to the real backend authentication flow through the `X-API-Key` header.

Before this implementation, the backend only accepted static environment keys from `API_KEYS`, while keys generated through `/settings/api-keys` were stored in user settings but were not verified by the main authentication dependency.

## Modified Files

```text
processual_api/auth/security.py
processual_api/routers/settings.py
processual_api/services/api_key_store.py
```

## Implementation Summary

The implementation added a transitional dynamic API key verification layer based on the existing local JSON settings storage.

The new flow is:

```text
X-API-Key
  -> verify dynamic pmk_ key first
  -> verify hash
  -> reject revoked, disabled, or expired keys
  -> resolve user_id, client_id, api_key_id, prefix, scopes, and session_type
  -> update last_used_at and usage_count
  -> allow request
```

The legacy `API_KEYS` environment fallback is still available, but only for local/development/test environments.

## Key Features Implemented

* Dynamic `pmk_` key verification.
* Secure hash verification using bcrypt or PBKDF2 fallback.
* No plaintext API key storage.
* API key prefix display.
* `last_used_at` update.
* `usage_count` update.
* Soft revoke using `status = revoked` and `revoked_at`.
* Rejection of revoked keys.
* User identity returned with:

  * `sub`
  * `user_id`
  * `client_id`
  * `role`
  * `auth_method`
  * `session_type`
  * `api_key_id`
  * `api_key_prefix`
  * `scopes`

## Test Evidence

### 1. Valid Dynamic API Key

Command:

```powershell
curl.exe -H "X-API-Key: pmk_..." http://127.0.0.1:8000/adapters/status
```

Result:

```text
PASS
```

The backend returned the adapters status payload.

### 2. Invalid API Key

Command:

```powershell
curl.exe -H "X-API-Key: pmk_wrong_key" http://127.0.0.1:8000/adapters/status
```

Result:

```json
{"detail":"Invalid API key"}
```

Status:

```text
PASS
```

### 3. Secure Storage

The local settings file showed:

```text
prefix
hashed
status
last_used_at
usage_count
```

The plaintext API key was not stored.

Status:

```text
PASS
```

### 4. Usage Tracking

After successful use, the key record showed:

```text
last_used_at = updated
usage_count = 3
```

Status:

```text
PASS
```

### 5. Revocation

Command:

```powershell
curl.exe -X DELETE -H "X-API-Key: pmk_..." http://127.0.0.1:8000/settings/api-keys/{key_id}
```

Result:

```json
{
  "status": "revoked",
  "id": "318bc627932ed728",
  "revoked_at": "2026-06-28T20:11:17.048010+00:00"
}
```

Status:

```text
PASS
```

### 6. Revoked Key Rejection

After revocation, the same API key was tested again.

Result:

```json
{"detail":"Invalid API key"}
```

Status:

```text
PASS
```

## Final Status

```text
KEY-01 Dynamic API Key Verification: PASS
```

Dynamic API keys are now connected to the real backend authentication flow.

The current JSON-based implementation is acceptable as a transitional local storage layer before moving API keys to PostgreSQL.

## Next Steps

```text
KEY-02 — Scopes Enforcement
KEY-03 — Usage Logs
KEY-04 — Quota Enforcement
KEY-05 — Plan / Subscription Binding
KEY-06 — PostgreSQL API Keys Table
```

## Security Note

The API key used during the test was exposed in the console log and was successfully revoked. It must not be reused.


---

## KEY-02 Addendum — Scope Enforcement

## Objective

The goal of KEY-02 was to ensure that a valid API key is not enough by itself. The key must also include the required scope for the requested endpoint.

## Implemented Change

A new `require_scope(required_scope)` dependency was added to:

```text
processual_api/auth/security.py
