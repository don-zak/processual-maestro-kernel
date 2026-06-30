# API Keys and Adapters Regression Coverage Report

## Processual Maestro Kernel v2.0.0

## Regression / QA Stabilization Phase

---

## 1. Purpose

This report documents the regression coverage added after completing the API Keys and Adapters hardening phases in **Processual Maestro Kernel v2.0.0**.

The goal of this phase is to prevent regressions before further feature development, especially around:

* Dynamic `pmk_` API keys
* API key creation, verification, revocation, usage tracking, scopes, plans, and quotas
* Adapter provider metadata
* Adapter configuration
* Adapter status reporting
* Adapter test readiness
* Unified adapter readiness scanning

This phase intentionally avoids live external provider dependencies in the core pytest suite. Tests must run without OpenAI, OpenRouter, Ollama, Gemini, Anthropic, or any other external service.

---

## 2. Current Regression Baseline

Latest verified baseline:

```text
30 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

The 6 warnings are development/security configuration warnings related to weak or missing deployment secrets and infrastructure values, including:

* `JWT_SECRET`
* `DATABASE_URL`
* `REDIS_URL`
* `POSTGRES_PASSWORD`
* `REDIS_PASSWORD`
* `GRAFANA_ADMIN_PASSWORD`

These warnings do not break the current regression suite, but they must be resolved before production deployment.

---

## 3. Regression Commit Chain

Current regression stabilization chain:

```text
fb33c25 TEST-04B add adapter test and readiness behavior regression tests
21664b0 TEST-04A add adapter configure and status regression tests
74e5ba3 TEST-03B add API key quota and plan regression tests
5bd18c5 TEST-03A add auth scope regression tests
6e392b0 TEST-02B add API key settings route regression tests
67ccca4 TEST-02A add API key store regression tests
48e908b ADAPTERS-01G add adapter readiness scanner with regression test
095ac8f TEST-01A add provider metadata and registry regression tests
827736e ADAPTERS-01F harden adapter test readiness scope
e22187c ADAPTERS-01E enrich adapter status metadata
67ea1cc ADAPTERS-01D centralize provider metadata
```

---

## 4. TEST-01A — Provider Metadata and Registry Regression

Commit:

```text
095ac8f TEST-01A add provider metadata and registry regression tests
```

Coverage:

* `provider_metadata.py`
* Provider IDs
* Provider environment mapping
* Public provider metadata
* Adapter registry availability
* Generic OpenAI-compatible adapter registration
* OpenRouter registration
* Test directory tracking through `.gitignore` correction

Purpose:

This test set ensures that provider metadata remains centralized and that adapters are not silently removed or broken from the registry.

---

## 5. ADAPTERS-01G — Unified Adapter Readiness Scanner

Commit:

```text
48e908b ADAPTERS-01G add adapter readiness scanner with regression test
```

Added endpoint:

```text
GET /adapters/readiness
```

Protection:

```text
admin:settings
```

Response fields protected by regression tests:

```text
providers
total
configured_count
ok_count
default
```

Per-provider fields:

```text
provider_id
display_name
kind
auth_mode
openai_compatible
base_url_configurable
default_base_url
api_key_env
model_env
url_env
provider
name
configured
ok
latency_ms
model
message
```

Purpose:

This endpoint gives administrators one unified readiness view for all adapters without having to test each provider manually.

---

## 6. TEST-02A — API Key Store Regression

Commit:

```text
67ccca4 TEST-02A add API key store regression tests
```

Coverage:

* `verify_dynamic_api_key`
* `pmk_` dynamic key acceptance
* Rejection of non-dynamic keys
* Rejection of incorrect keys
* Rejection of revoked keys
* Hash-only storage validation
* No plain key persistence
* `usage_count` increment
* `last_used_at` update

Purpose:

This protects the core runtime path where incoming `pmk_` API keys are verified and usage is recorded.

---

## 7. TEST-02B — API Key Settings Route Regression

Commit:

```text
6e392b0 TEST-02B add API key settings route regression tests
```

Coverage:

* API key creation
* One-time return of the plain API key
* Hash-only persistence
* Client/user/label persistence
* Default scopes
* Initial quota state
* Revocation without hard deletion
* Admin scope protection for API key settings routes

Protected routes:

```text
GET /settings/api-keys
POST /settings/api-keys
PATCH /settings/api-keys/{key_id}/plan
PATCH /settings/api-keys/{key_id}/quota
DELETE /settings/api-keys/{key_id}
```

Purpose:

This prevents regressions where API keys might be hard-deleted, stored in plain text, or exposed beyond the creation response.

---

## 8. TEST-03A — Auth Scope Regression

Commit:

```text
5bd18c5 TEST-03A add auth scope regression tests
```

Coverage:

Adapter routes:

```text
/adapters/status      -> read:adapters
/adapters/configure   -> admin:settings
/adapters/readiness   -> admin:settings
/adapters/test        -> admin:settings
```

Settings routes:

```text
/settings/plans
/settings/api-keys
/settings/api-keys/{key_id}/plan
/settings/api-keys/{key_id}/quota
```

Purpose:

This ensures sensitive routes do not fall back to simple authenticated-user access and remain protected by explicit scopes.

---

## 9. TEST-03B — API Key Quota and Plan Regression

Commit:

```text
74e5ba3 TEST-03B add API key quota and plan regression tests
```

Coverage:

* Plan rebinding
* Quota limit update from plan
* Clearing manual quota override when plan changes
* Manual quota override set
* Manual quota override clear
* `quota_remaining` calculation
* Unlimited quota behavior
* `quota_rejected_count` preservation
* `quota_policy_source`

Purpose:

This protects KEY-04 and KEY-05 behavior around quota enforcement, plan/subscription binding, and manual quota overrides.

---

## 10. TEST-04A — Adapter Configure and Status Regression

Commit:

```text
21664b0 TEST-04A add adapter configure and status regression tests
```

Coverage:

* `generic_openai_compatible` configuration
* Provider environment mapping
* Runtime `os.environ` application
* Model environment variable update
* Base URL environment variable update
* Unknown provider rejection
* `/adapters/status` metadata response

Protected behavior:

```text
provider_env_map
provider_public_metadata
/adapters/configure
/adapters/status
```

Purpose:

This prevents regressions in customer-owned provider configuration, especially for OpenAI-compatible endpoints such as Ollama, LM Studio, vLLM, and private enterprise endpoints.

---

## 11. TEST-04B — Adapter Test and Readiness Behavior Regression

Commit:

```text
fb33c25 TEST-04B add adapter test and readiness behavior regression tests
```

Coverage:

`/adapters/test`:

* Unknown provider returns 404
* Successful adapter test returns metadata
* Successful adapter test returns `ok=True`
* Successful adapter test returns `message=Connected`
* Adapter exception returns `ok=False`
* Adapter exception returns `message=Adapter error: <ExceptionType>`
* Latency is returned as integer milliseconds

`/adapters/readiness`:

* Summarizes all adapters
* Calculates `total`
* Calculates `configured_count`
* Calculates `ok_count`
* Returns default adapter name
* Preserves provider metadata
* Handles connected, unreachable, and exception cases

Purpose:

This protects readiness behavior without calling real external providers.

---

## 12. Current Protected Surface

The regression suite now covers:

```text
Provider metadata
Adapter registry
Adapter status
Adapter configuration
Adapter test readiness
Unified adapter readiness scanner
Dynamic API key verification
API key creation
API key revocation
API key usage tracking
API key scopes
API key plan binding
API key quota override
API key quota summary
Sensitive route scope protection
```

---

## 13. Important Testing Rule

The core pytest suite must remain independent from external provider availability.

Allowed in core pytest:

```text
Unit tests
Static regression tests
Monkeypatched route tests
Mocked adapter behavior
Temporary JSON stores
```

Not allowed in core pytest:

```text
Real OpenAI calls
Real OpenRouter calls
Real Ollama calls
Real Gemini calls
Real Anthropic calls
Network-dependent provider readiness
```

Live provider checks should remain separate as smoke tests or manual operational proofs.

---

## 14. Recommended Next Steps

### TEST-05A — Persistence Safety Regression

Suggested coverage:

* JSON save uses temporary file replacement
* Corrupt JSON load returns safe empty state
* Revoked keys remain in storage
* Backup behavior remains documented and protected where applicable

### TEST-05B — Settings Storage Regression

Suggested coverage:

* `_load_raw`
* `_save_raw`
* settings file naming
* user-specific settings isolation
* API key list behavior when missing or malformed

### TEST-06A — Optional Smoke Script Documentation

Suggested coverage:

* Manual PowerShell smoke commands for:

  * Create admin/client API key
  * Configure generic OpenAI-compatible adapter
  * Test adapter
  * Read `/adapters/readiness`
  * Confirm scope rejection with client key

### DOCS-PROD-01 — Production Security Readiness

Suggested coverage:

* Replace weak `JWT_SECRET`
* Configure strong `DATABASE_URL`
* Configure strong `REDIS_URL`
* Configure database and Redis passwords
* Configure Grafana admin password
* Confirm no dev-only secrets are used before deployment

---

## 15. Standard Verification Commands

Before every commit in this stabilization phase:

```powershell
python -m pytest -q
python -m compileall .\tests .\processual_api .\processual_kernel .\cgtlib
git diff --check
git status --short
```

Expected current result:

```text
30 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

---

## 16. Conclusion

The API Keys and Adapters phases have moved from feature completion into regression-protected stabilization.

The current branch is no longer only a feature branch for provider registration. It now contains a meaningful regression suite that protects the customer-facing access layer, provider configuration layer, adapter readiness layer, and quota/plan binding logic.

The next safest direction is to continue increasing regression coverage before adding new product features.


## TEST-05A — Settings Persistence Safety Regression

Commit:

```text
3243b7f TEST-05A add settings persistence safety regression tests
```

Latest verified baseline after this commit:

```text
35 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* `_load_raw` returns a safe empty dictionary when the settings file is missing.
* `_load_raw` returns a safe empty dictionary when the settings JSON is corrupt.
* `_save_raw` writes through a temporary `.tmp` file before replacing the main settings file.
* `_save_raw` creates a `.bak` backup when replacing an existing settings file.
* `_save_raw` cleans the temporary file after saving.
* `api_key_store._safe_load_json` safely handles corrupt JSON.
* `api_key_store._safe_save_json` writes JSON safely through temporary-file replacement.
* User settings persistence remains isolated through `settings_<user_id>.json`.

Protected behavior:

```text
_settings_path
_load_raw
_save_raw
_safe_load_json
_safe_save_json
.tmp replacement
.bak backup creation
corrupt JSON recovery
temporary file cleanup
```

Purpose:

This test protects the KEY-10 persistence hardening work. It ensures that settings and API key storage remain safe against corrupt JSON, interrupted writes, unsafe direct replacement, and accidental loss of the previous settings state. The settings router already uses `settings_<user_id>.json`, temporary write files, `.bak` backup creation, and `replace`-based persistence, and this regression test now locks that behavior in place.


## TEST-06A — CGT Governor Route Boundary Regression

Commit:

```text
af7666c TEST-06A add CGT governor route boundary regression tests
```

Latest verified baseline after this commit:

```text
41 passed, 6 warnings
compileall: PASS
git diff --check: PASS
```

Coverage:

* `/cgt/govern` remains protected by `require_quota("evaluation")`.
* Core governor routes remain authenticated.
* Report and PDF routes remain authenticated.
* Simulation routes remain authenticated.
* Governance gateway routes remain authenticated.
* The main governor router remains wired to `eval_store`.
* The main governor router remains wired to `PolicyContext` and `runtime_policy_engine`.
* The main governor router remains wired to `sign_response`.
* The main governor router remains wired to `encrypt_log_entry` and `decrypt_log_entry`.
* `_evaluate_and_record` keeps the policy decision, policy recording, signature generation, encrypted log entry, and evaluation storage hooks.

Protected behavior:

```text
/cgt/govern
/cgt/govern/batch
/cgt/govern/status
/cgt/govern/toggle
/cgt/govern/metrics
/cgt/govern/reports
/cgt/govern/reports/export
/cgt/govern/repair
/cgt/govern/auto-repair
/cgt/govern/compare
/cgt/govern/report
/cgt/analyze
/cgt/govern/gateway/*
require_quota("evaluation")
get_current_user authentication boundary
eval_store
runtime_policy_engine
sign_response
encrypt_log_entry
decrypt_log_entry
```

Purpose:

This test begins regression coverage for the broader CGT Governor surface beyond API Keys and Adapters. It does not yet change authorization rules or business logic; instead, it freezes the current route boundary map so future hardening can be deliberate and visible. In particular, it documents that `/cgt/govern` is quota-protected, while many other compute-heavy or report-producing routes currently rely on authenticated-user access. This creates a clear baseline for a later hardening phase such as `AUTH-HARDEN-01`.
