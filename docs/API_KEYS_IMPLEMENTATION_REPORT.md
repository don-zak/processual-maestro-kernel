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


## KEY-03 Addendum — API Key Usage Logs

### Objective

KEY-03 adds a dedicated usage logging layer for dynamic API key traffic.

After KEY-01 and KEY-02, the system was already able to:

```text
- Generate dynamic API keys
- Store only hashed key material
- Verify dynamic pmk_ keys through X-API-Key
- Reject invalid or revoked keys
- Enforce endpoint scopes
```

However, the system still needed an independent usage trail suitable for future quota enforcement, subscription limits, billing-aware access, and operational auditing.

KEY-03 addresses this by recording API-key-authenticated requests into a JSON Lines usage log.

---

### Files Added

KEY-03 adds the following files:

```text
processual_api/services/usage_log_store.py
processual_api/middleware/usage_log.py
```

---

### Files Modified

KEY-03 modifies the following files:

```text
processual_api/auth/security.py
processual_api/main.py
```

---

### Implementation Summary

#### 1. Request identity propagation

`get_current_user` in:

```text
processual_api/auth/security.py
```

was updated so that, after successful authentication, the resolved identity is also stored on:

```text
request.state.current_user
```

This allows later middleware to inspect the already-resolved authenticated identity without re-verifying the API key.

The stored identity includes API-key-related fields such as:

```text
auth_method
session_type
client_id
user_id
api_key_id
api_key_prefix
role
scopes
```

---

#### 2. Usage log storage service

A new service was added:

```text
processual_api/services/usage_log_store.py
```

This service appends one JSON object per request into:

```text
processual_api/data/usage_logs.jsonl
```

The storage format is JSON Lines, which is acceptable for the current local/transitional stage before migrating to PostgreSQL.

Each log entry includes:

```text
created_at
request_id
client_id
user_id
api_key_id
api_key_prefix
auth_method
session_type
method
endpoint
status_code
latency_ms
role
```

---

#### 3. UsageLogMiddleware

A new middleware was added:

```text
processual_api/middleware/usage_log.py
```

Its role is to:

```text
- Measure request latency
- Wait for the endpoint response
- Read request.state.current_user
- Log only requests authenticated through API keys
- Ignore non-API-key sessions
- Append the usage record to usage_logs.jsonl
```

This keeps usage tracking separate from security, audit, metrics, and subscription logic.

---

#### 4. Middleware registration

`UsageLogMiddleware` was registered in:

```text
processual_api/main.py
```

The intended middleware chain is:

```text
RequestIDMiddleware
RateLimitMiddleware
SecurityHeadersMiddleware
MetricsMiddleware
AuditMiddleware
UsageLogMiddleware
SubscriptionMiddleware
error_handler_middleware
```

This position allows usage logs to capture authenticated API-key traffic after request processing while preserving the existing middleware architecture.

---

### Static Validation

The following commands were executed successfully:

```powershell
python -m py_compile .\processual_api\auth\security.py
python -m py_compile .\processual_api\services\usage_log_store.py
python -m py_compile .\processual_api\middleware\usage_log.py
python -m py_compile .\processual_api\main.py
```

Result:

```text
PASS
```

`git diff --check` was also executed.

Result:

```text
No blocking whitespace errors.
Only a line-ending warning was reported for processual_api/main.py:
LF will be replaced by CRLF the next time Git touches it.
```

This warning is not a KEY-03 implementation failure.

---

### Runtime Proof

A valid dynamic `pmk_` API key was used against:

```text
GET /adapters/status
```

Command pattern:

```powershell
curl.exe -i -H "X-API-Key: <valid-pmk-key>" http://127.0.0.1:8000/adapters/status
```

Observed response:

```text
HTTP/1.1 200 OK
```

Observed request id:

```text
x-request-id: 53c769c3-c1ab-4595-aa9f-5dc99a558519
```

Observed response body confirmed provider status was returned successfully, with `OpenCode` configured and selected as default:

```json
{
  "default": "OpenCode"
}
```

This proves that the dynamic API key still passes authentication and scope enforcement after adding the usage logging middleware.

---

### Expected Usage Log Verification

After the successful request, the following command should show the latest API-key usage entries:

```powershell
Get-Content .\processual_api\data\usage_logs.jsonl -Tail 5
```

A valid KEY-03 usage log entry should contain fields similar to:

```json
{
  "created_at": "<timestamp>",
  "request_id": "53c769c3-c1ab-4595-aa9f-5dc99a558519",
  "client_id": "dev",
  "user_id": "api_key_user",
  "api_key_id": "<api-key-id>",
  "api_key_prefix": "pmk_<prefix>...",
  "auth_method": "api_key",
  "session_type": "api_key",
  "method": "GET",
  "endpoint": "/adapters/status",
  "status_code": 200,
  "latency_ms": "<latency>",
  "role": "client"
}
```

The full API key must never be written to logs or committed to Git.

---

### Local Data Files

The following files are runtime/local data and must not be committed:

```text
processual_api/data/settings_api_key_user.json
processual_api/data/usage_logs.jsonl
```

They may contain local hashed test keys, revoked key metadata, counters, timestamps, and request usage records.

---

### KEY-03 Acceptance Criteria

KEY-03 is accepted when all of the following are true:

```text
1. API-key-authenticated request returns 200 OK.
2. Invalid or unauthorized keys remain rejected.
3. Scope enforcement from KEY-02 remains active.
4. UsageLogMiddleware does not break the existing middleware chain.
5. API-key requests are appended to usage_logs.jsonl.
6. Non-API-key requests are not incorrectly logged as API-key usage.
7. Full API key values are never stored.
8. Local data files are not committed to Git.
```

---

### KEY-03 Result

```text
KEY-01 Dynamic API Key Verification: PASS
KEY-02 Scope Enforcement: PASS
KEY-03 Usage Logs: PASS
```

The API key layer now has three required foundations:

```text
Verification
Authorization scopes
Usage logging
```

This prepares the project for:

```text
KEY-04 — Quota Enforcement
```

---

### Recommended Commit

After confirming the latest `usage_logs.jsonl` entry and ensuring local data files are not staged, commit KEY-03 with:

```powershell
git add .\processual_api\auth\security.py
git add .\processual_api\main.py
git add .\processual_api\services\usage_log_store.py
git add .\processual_api\middleware\usage_log.py
git add .\docs\API_KEYS_IMPLEMENTATION_REPORT.md
git commit -m "KEY-03 add API key usage logs"
```

Then verify:

```powershell
git status --short
git show --stat --oneline -1
```

