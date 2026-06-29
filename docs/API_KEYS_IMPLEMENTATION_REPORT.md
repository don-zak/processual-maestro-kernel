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

## KEY-04 Addendum — API Key Quota Enforcement

### Objective

KEY-04 introduces the first quota enforcement layer for dynamic API keys.

After KEY-01, KEY-02, and KEY-03, the API key system already supported:

```text
Dynamic API key verification
Hashed key storage
Soft revoke
Scope enforcement
API key usage logs
```

KEY-04 adds the next required commercial control:

```text
Quota enforcement
```

The purpose is to prevent API-key clients from exceeding their allowed usage limit.

This first implementation is intentionally transitional and JSON-backed. It is designed to validate the quota logic locally before moving to PostgreSQL, subscription plans, billing-aware access, or cloud deployment.

---

### Files Added

KEY-04 adds:

```text
processual_api/services/quota_store.py
```

---

### Files Modified

KEY-04 modifies:

```text
processual_api/auth/security.py
processual_api/routers/cgt_governor.py
```

---

### Design Decision

Quota enforcement was implemented as a dependency, not as a global middleware.

This is intentional because the authenticated identity is resolved through FastAPI dependencies. A middleware running before endpoint dependencies would not reliably have access to:

```text
request.state.current_user
```

Therefore KEY-04 adds a dependency-based quota gate:

```text
require_quota("evaluation")
```

This allows quota enforcement to be applied only to selected commercial endpoints.

---

### Initial Counted Endpoint

KEY-04 does not count every endpoint.

The first counted commercial endpoint is:

```text
POST /cgt/govern
```

The following endpoint was explicitly tested and remains non-counted:

```text
GET /adapters/status
```

This preserves the ability to inspect adapter status without consuming commercial quota.

---

### Quota Store

The new quota service is:

```text
processual_api/services/quota_store.py
```

It provides a small JSON-backed quota layer that:

```text
Reads local settings_*.json files
Finds the current api_key_id
Initializes quota_limit when missing
Initializes quota_scope when missing
Increments quota_used for counted endpoints
Stores quota_last_used_at
Rejects exceeded quota with HTTP 429
Stores quota_last_rejected_at
Increments quota_rejected_count
```

The default quota limit is:

```text
50
```

It can be overridden by environment variable:

```text
PMK_DEFAULT_API_KEY_QUOTA_LIMIT
```

---

### Security Dependency

`processual_api/auth/security.py` now exposes:

```text
require_quota(quota_scope: str = "evaluation")
```

This dependency:

```text
Uses get_current_user
Reads the current request method and path
Calls consume_quota
Updates request.state.current_user
Returns the quota-checked user identity
```

This keeps KEY-01 authentication and KEY-02 scope enforcement intact.

---

### Router Binding

`processual_api/routers/cgt_governor.py` was updated so that:

```text
POST /cgt/govern
```

uses:

```text
Depends(require_quota("evaluation"))
```

instead of only:

```text
Depends(get_current_user)
```

No other CGT endpoints were quota-bound in this phase.

---

### Runtime Proof — Non-counted Endpoint

A valid dynamic `pmk_` API key was used against:

```text
GET /adapters/status
```

Observed result:

```text
HTTP/1.1 200 OK
```

Then the local API key settings file was checked for quota fields.

Observed result:

```text
No quota_used / quota_limit / quota_scope was created by /adapters/status
```

Conclusion:

```text
/adapters/status remains non-counted: PASS
```

---

### Runtime Proof — Quota Consumption

A valid dynamic `pmk_` API key was used against:

```text
POST /cgt/govern
```

with a valid JSON request body.

After the first successful request, the local API key record showed:

```text
quota_limit = 50
quota_scope = evaluation
quota_used = 1
quota_last_used_at = 2026-06-29T10:23:22.859266+00:00
```

After a second successful request, the local API key record showed:

```text
quota_limit = 50
quota_scope = evaluation
quota_used = 2
quota_last_used_at = 2026-06-29T10:24:43.627150+00:00
```

Conclusion:

```text
/cgt/govern consumes quota correctly: PASS
```

---

### Runtime Proof — Quota Rejection

For rejection testing, the local test key quota limit was temporarily reduced to:

```text
quota_limit = 2
```

while:

```text
quota_used = 2
```

A third request to:

```text
POST /cgt/govern
```

returned:

```text
HTTP/1.1 429 Too Many Requests
```

Observed response:

```json
{
  "detail": {
    "error": "quota_exceeded",
    "quota_scope": "evaluation",
    "quota_limit": 2,
    "quota_used": 2
  }
}
```

Observed request id:

```text
6d1c7454-faa4-411d-878f-7de8aca6ecd4
```

The local API key record then showed:

```text
quota_last_rejected_at = 2026-06-29T10:26:58.222776+00:00
quota_rejected_count = 1
quota_used = 2
```

Conclusion:

```text
Quota rejection works correctly: PASS
```

---

### Usage Log Proof

The existing KEY-03 usage log system also recorded the quota tests.

Observed successful quota-counted entries:

```text
POST /cgt/govern
status_code = 200
quota_used increased to 1 and then 2
```

Observed rejected quota entry:

```text
request_id = 6d1c7454-faa4-411d-878f-7de8aca6ecd4
method = POST
endpoint = /cgt/govern
status_code = 429
auth_method = api_key
```

Conclusion:

```text
KEY-03 usage logs correctly capture KEY-04 quota rejection: PASS
```

---

### Static Validation

The following commands were executed successfully:

```powershell
python -m py_compile .\processual_api\services\quota_store.py
python -m py_compile .\processual_api\auth\security.py
python -m py_compile .\processual_api\routers\cgt_governor.py
git diff --check
```

Result:

```text
PASS
```

---

### Local Test Data

The following file was modified during local runtime testing:

```text
processual_api/data/settings_api_key_user.json
```

It contains local quota counters and test key metadata.

This file must not be committed.

The temporary request body file was removed:

```text
tmp-govern-body.json
```

The following runtime usage log was also used for proof:

```text
processual_api/data/usage_logs.jsonl
```

This file must not be committed.

---

### KEY-04 Acceptance Criteria

KEY-04 is accepted when all of the following are true:

```text
1. A valid API key can still access /adapters/status.
2. /adapters/status does not consume quota.
3. A valid API key can call POST /cgt/govern when quota is available.
4. POST /cgt/govern increments quota_used.
5. Exceeding quota returns HTTP 429.
6. The 429 response includes quota_exceeded details.
7. The key record stores quota_last_rejected_at.
8. The key record increments quota_rejected_count.
9. usage_logs.jsonl records both successful and rejected API-key requests.
10. Local runtime data files are not committed.
```

---

### KEY-04 Result

```text
KEY-04 Quota Enforcement: PASS
```

The API key layer now has four foundations:

```text
Verification
Authorization scopes
Usage logging
Quota enforcement
```

This prepares the project for:

```text
KEY-05 — Plan / Subscription Binding
```

---

### Recommended Commit

After confirming that only source/report files are staged, commit KEY-04 with:

```powershell
git add .\processual_api\auth\security.py
git add .\processual_api\routers\cgt_governor.py
git add .\processual_api\services\quota_store.py
git add .\docs\API_KEYS_IMPLEMENTATION_REPORT.md
git commit -m "KEY-04 add API key quota enforcement"
```

Then verify:

```powershell
git status --short
git show --stat --oneline -1
```

## KEY-05 Addendum — Plan / Subscription Binding

### Objective

KEY-05 introduces the first local plan/subscription binding layer for API key quotas.

After KEY-04, quota enforcement was already working on:

```text
POST /cgt/govern
```

However, the quota limit was still effectively local/default-driven.

KEY-05 changes this by binding API key quota limits to a local plan policy. This keeps the system simple and JSON-backed before PostgreSQL, payment providers, external billing, or cloud deployment.

---

### Files Added

KEY-05 adds:

```text
processual_api/services/plan_store.py
```

---

### Files Modified

KEY-05 modifies:

```text
processual_api/routers/settings.py
processual_api/services/quota_store.py
```

---

### Plan Store

A new local plan policy store was added:

```text
processual_api/services/plan_store.py
```

It defines local plan policies and quota limits.

Initial plans:

```text
pilot_starter        evaluation quota = 50
pilot_pro            evaluation quota = 500
institution_trial    evaluation quota = 2000
enterprise_private   evaluation quota = -1
```

In the current quota logic:

```text
-1 means unlimited
```

The plan store provides:

```text
resolve_plan_id
get_plan_policy
quota_limit_for_plan
```

It also supports aliases such as:

```text
Starter -> pilot_starter
Pro -> pilot_pro
Institution -> institution_trial
Enterprise -> enterprise_private
```

---

### Settings Router Binding

`processual_api/routers/settings.py` was updated so that newly created API keys now receive plan and quota metadata at creation time.

New API key records include:

```text
plan_id
quota_policy
quota_scope
quota_limit
quota_used
quota_reset_at
```

The API key creation response now also returns:

```text
plan_id
quota_policy
quota_scope
quota_limit
quota_used
```

This allows the client console and future commercial UI to display the quota state immediately after creating a key.

---

### API Key Listing

`GET /settings/api-keys` now exposes quota-related metadata for visible non-revoked API keys:

```text
plan_id
quota_scope
quota_limit
quota_used
quota_rejected_count
```

This makes the local API key management view plan-aware and quota-aware.

---

### Quota Store Binding

`processual_api/services/quota_store.py` was updated so that quota enforcement can resolve the effective quota limit from the key plan.

Resolution order:

```text
1. Manual override if quota_limit_override exists or quota_policy.source = manual
2. Key-level plan_id / plan
3. Local subscription plan_id / plan
4. Starter fallback
```

When plan-driven quota is used, the key record is updated with:

```text
plan_id
quota_policy
quota_limit
quota_scope
```

This keeps older keys compatible while allowing new and updated keys to become plan-bound.

---

### Runtime Proof — API Key Creation

A valid dynamic API key was used to create a new API key through:

```text
POST /settings/api-keys
```

Observed response:

```text
HTTP/1.1 200 OK
```

The response included:

```text
id = 987d23e9b6146a6a
plan_id = pilot_starter
quota_policy.source = plan
quota_policy.quotas.evaluation = 50
quota_scope = evaluation
quota_limit = 50
quota_used = 0
```

Conclusion:

```text
New API keys are created with plan-bound quota metadata: PASS
```

---

### Runtime Proof — Local Key Record

The local API key settings file showed the newly created key with:

```text
plan_id = pilot_starter
quota_policy present
quota_scope = evaluation
quota_limit = 50
quota_used = 0
```

Conclusion:

```text
Plan metadata is persisted in the local key record: PASS
```

---

### Runtime Proof — Plan Upgrade to pilot_pro

For local proof, the new key was updated from:

```text
pilot_starter
```

to:

```text
pilot_pro
```

Then a request was sent to:

```text
POST /cgt/govern
```

Observed result:

```text
HTTP/1.1 200 OK
```

The local key record then showed:

```text
plan_id = pilot_pro
quota_limit = 500
quota_used = 1
```

Conclusion:

```text
quota_store resolves pilot_pro to quota_limit 500: PASS
```

---

### Runtime Proof — API Key Listing

A request was sent to:

```text
GET /settings/api-keys
```

Observed result:

```text
HTTP/1.1 200 OK
```

The response included plan/quota fields for visible keys, including the new key:

```text
id = 987d23e9b6146a6a
plan_id = pilot_pro
quota_scope = evaluation
quota_limit = 500
quota_used = 1
quota_rejected_count = 0
```

Conclusion:

```text
/settings/api-keys is now plan-aware and quota-aware: PASS
```

---

### Usage Log Proof

The existing KEY-03 usage log recorded KEY-05 activity.

Observed entries included:

```text
POST /settings/api-keys     status_code = 200
POST /cgt/govern            status_code = 200
GET /settings/api-keys      status_code = 200
```

For the newly created key:

```text
api_key_id = 987d23e9b6146a6a
api_key_prefix = pmk_yNcXwwmo...
endpoint = /cgt/govern
status_code = 200
```

Conclusion:

```text
KEY-03 usage logging remains compatible with KEY-05 plan binding: PASS
```

---

### Static Validation

The following commands were executed successfully:

```powershell
python -m py_compile .\processual_api\services\plan_store.py
python -m py_compile .\processual_api\services\quota_store.py
python -m py_compile .\processual_api\routers\settings.py
git diff --check
```

Result:

```text
PASS
```

---

### Local Test Data

The following local runtime files were used for proof only and must not be committed:

```text
processual_api/data/settings_api_key_user.json
processual_api/data/usage_logs.jsonl
```

A temporary request body file was removed:

```text
tmp-govern-body.json
```

---

### KEY-05 Acceptance Criteria

KEY-05 is accepted when all of the following are true:

```text
1. plan_store.py defines local plan policies.
2. New API keys receive plan_id and quota_policy.
3. New API keys receive quota_scope, quota_limit, and quota_used.
4. pilot_starter resolves to quota_limit 50.
5. pilot_pro resolves to quota_limit 500.
6. quota_store consumes quota using plan-derived limits.
7. /settings/api-keys exposes plan/quota metadata.
8. Existing KEY-03 usage logging continues to work.
9. Existing KEY-04 quota enforcement continues to work.
10. Runtime data files are not committed.
```

---

### KEY-05 Result

```text
KEY-05 Plan / Subscription Binding: PASS
```

The API key layer now has five foundations:

```text
Verification
Authorization scopes
Usage logging
Quota enforcement
Plan / subscription binding
```

This prepares the project for:

```text
KEY-06 — Admin quota controls and plan management
```

or, if commercial deployment is prioritized:

```text
Cloud Run readiness + managed persistence
```

---

### Recommended Commit

After confirming that only source/report files are staged, commit KEY-05 with:

```powershell
git add .\processual_api\routers\settings.py
git add .\processual_api\services\quota_store.py
git add .\processual_api\services\plan_store.py
git add .\docs\API_KEYS_IMPLEMENTATION_REPORT.md
git commit -m "KEY-05 bind API key quotas to plans"
```

Then verify:

```powershell
git status --short
git show --stat --oneline -1
```


# KEY-06 — Admin Plan and Quota Controls

## الهدف

بعد KEY-05 أصبح نظام الحصص مرتبطًا بالخطط، لكن تغيير خطة مفتاح API أو تعيين حصة يدوية كان لا يزال يتطلب تعديل JSON محليًا.

هدف KEY-06 هو إضافة endpoints إدارية آمنة تسمح بإدارة الخطط والحصص من داخل API نفسه، دون Billing، ودون Stripe، ودون Cloud، ودون PostgreSQL.

## الملفات المعدلة

```text
processual_api/routers/settings.py
```

## ما تم تنفيذه

تمت إضافة نماذج طلبات إدارية:

```text
ApiKeyPlanUpdate
ApiKeyQuotaUpdate
```

وتمت إضافة helper functions:

```text
_find_active_api_key_or_404
_api_key_quota_summary
```

وتمت إضافة endpoints جديدة:

```text
GET /settings/plans
PATCH /settings/api-keys/{key_id}/plan
PATCH /settings/api-keys/{key_id}/quota
```

## GET /settings/plans

يعرض الخطط المحلية المتاحة:

```text
pilot_starter        evaluation quota = 50
pilot_pro            evaluation quota = 500
institution_trial    evaluation quota = 2000
enterprise_private   evaluation quota = -1
```

حيث:

```text
-1 = unlimited
```

## PATCH /settings/api-keys/{key_id}/plan

يسمح بتغيير خطة مفتاح API باستعمال `key_id` الداخلي، وليس المفتاح الكامل الذي يبدأ بـ `pmk_`.

تم إثبات تغيير المفتاح:

```text
key_id = 9b377b0fc4270102
plan_id = pilot_pro
quota_limit = 500
quota_policy_source = plan
quota_used = 2
quota_remaining = 498
```

الحكم:

```text
PATCH plan: PASS
pilot_pro quota resolution: PASS
```

## PATCH /settings/api-keys/{key_id}/quota

يسمح بتعيين override يدوي للحصة:

```json
{
  "quota_limit_override": 100
}
```

وكانت النتيجة:

```text
quota_limit = 100
quota_limit_override = 100
quota_policy_source = manual
quota_remaining = 98
```

ثم تم حذف override بإرسال:

```json
{
  "quota_limit_override": null
}
```

وكانت النتيجة:

```text
quota_limit = 500
quota_policy_source = plan
quota_limit_override = null
quota_remaining = 498
```

الحكم:

```text
manual override: PASS
clear override back to plan: PASS
```

## إثبات استمرار quota enforcement

تم تنفيذ:

```text
POST /cgt/govern
```

بعد تعديلات KEY-06، وكانت النتيجة ناجحة وأرجعت تقييمًا يحتوي:

```text
eval_id
governance_action
scores
policy
```

ثم تم عرض المفاتيح، وظهر أن:

```text
quota_used before = 2
quota_used after  = 3
```

الحكم:

```text
/cgt/govern still consumes evaluation quota: PASS
```

## إثبات usage logs

أظهر `usage_logs.jsonl` تسجيل الطلبات التالية عبر API key:

```text
PATCH /settings/api-keys/9b377b0fc4270102/plan -> 200
PATCH /settings/api-keys/9b377b0fc4270102/quota -> 200
GET /settings/plans -> 200
POST /cgt/govern -> 200
GET /settings/api-keys -> 200
```

كل السجلات احتوت:

```text
auth_method = api_key
session_type = api_key
api_key_id
api_key_prefix
request_id
status_code
latency_ms
```

الحكم:

```text
usage logs remain compatible with KEY-06: PASS
```

## الفحوصات

تم تنفيذ:

```powershell
python -m py_compile .\processual_api\routers\settings.py
git diff --check
```

والنتيجة:

```text
PASS
```

كما تم حذف الملف المؤقت:

```text
tmp-key06-plan.json
```

وحالة Git قبل تحديث التقرير:

```text
M processual_api/routers/settings.py
```

## الحكم النهائي

```text
KEY-06 Admin Plan and Quota Controls: PASS
```

أصبحت طبقة API Keys التجارية المحلية تشمل الآن:

```text
KEY-01 Dynamic API Key Verification
KEY-02 Scope Enforcement
KEY-03 Usage Logs
KEY-04 Quota Enforcement
KEY-05 Plan / Subscription Binding
KEY-06 Admin Plan and Quota Controls
```

## KEY-07 — Admin Scope Hardening

### الهدف

تهدف KEY-07 إلى تأمين مسارات الإدارة الخاصة بطبقة مفاتيح API، ومنع مفاتيح العملاء العادية من الوصول إلى عمليات الإدارة الحساسة.

قبل KEY-07 كانت بعض مسارات الإعدادات تعتمد فقط على:

```python
Depends(get_current_user)

















