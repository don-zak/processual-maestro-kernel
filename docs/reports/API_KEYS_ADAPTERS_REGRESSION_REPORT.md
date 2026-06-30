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
85 passed, 6 warnings
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


## TEST-06B — CGT Governor Behavior Regression

Commit:

```text
a733430 TEST-06B add CGT governor behavior regression tests
```

Verified baseline after this commit:

```text
44 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* `_evaluate_and_record`
* `runtime_policy_engine.decide`
* `runtime_policy_engine.record`
* `sign_response`
* `encrypt_log_entry`
* `eval_store.append`
* `governor_status`
* `governor_toggle`
* `/cgt/analyze`

Purpose:

This test protects the behavior path where CGT Governor answers are evaluated, signed, recorded, encrypted, and stored. It uses controlled fake score inputs and fake stores so that no external provider or private engine is required.

---

## TEST-07A — Evaluation Store Regression

Commit:

```text
6b634ea TEST-07A add evaluation store regression tests
```

Verified baseline after this commit:

```text
47 passed, 6 warnings
compileall: PASS
git diff --check: PASS
```

Coverage:

* Append dictionary entries.
* Append JSON string entries.
* Preserve existing `eval_id`.
* Generate missing `eval_id`.
* Persist UTF-8 content.
* Load existing JSONL entries.
* Skip malformed JSONL lines.
* Enforce `maxlen` behavior.
* Extend multiple entries.
* Clear store.
* Preserve `path` property behavior.

Purpose:

This protects the JSONL evaluation store used by CGT Governor reports and audit history.

---

## TEST-07B — Governor Reports Regression

Commit:

```text
4f4a649 TEST-07B add governor reports regression tests
```

Verified baseline after this commit:

```text
52 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* `/cgt/govern/reports`
* `/cgt/govern/reports/export`
* `/cgt/govern/reports/pdf`
* `/cgt/govern/reports/{eval_id}/pdf`
* `/cgt/govern/report`
* JSON export headers
* PDF response path
* Base64 PDF report path
* Missing `eval_id` 404 behavior

Purpose:

This protects the reporting layer without requiring real PDF generation during tests. The PDF function is monkeypatched so that the route behavior remains covered while avoiding heavy external dependencies.

---

## TEST-08A — Security and Crypto Regression

Commit:

```text
d0e829d TEST-08A add security and crypto regression tests
```

Verified baseline after this commit:

```text
61 passed, 6 warnings
compileall: PASS
git diff --check: PASS
```

Coverage:

* `sign_response`
* `sign_bytes`
* Canonical JSON behavior
* SHA-256 and SHA3-256 hash helpers
* AES-GCM encryption/decryption
* ChaCha20Poly1305 encryption/decryption
* Envelope building and verification
* Encrypted report rotation
* Guard fallback behavior
* Guard encrypted round trip
* KeyRing environment key loading
* SecurityPolicy defaults

Purpose:

This protects the cryptographic and signing layer used by governance reports, logs, and secure report envelopes.

---

## TEST-09A — Middleware Regression

Commit:

```text
fbca56f TEST-09A add middleware regression tests
```

Verified baseline after this commit:

```text
68 passed, 7 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* `RequestIDMiddleware`
* `SecurityHeadersMiddleware`
* `RateLimitMiddleware`
* `AuditMiddleware`
* `UsageLogMiddleware`
* `SubscriptionMiddleware`
* `error_handler_middleware`

Protected behavior:

* `X-Request-ID` propagation
* Security headers
* Redis-backed rate limit behavior with fake Redis
* 429 rate-limit response
* Audit log emission
* API-key usage log append
* Subscription stage computation
* Grace/suspended/expired handling boundaries
* Generic 500 error response

Note:

This step introduced one additional warning:

```text
StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.
```

This warning is test-client related and does not indicate a runtime failure. It can be handled later during dependency modernization.

---

## TEST-10A — FastAPI Integration Smoke Tests

Commit:

```text
e2a5e9e TEST-10A add FastAPI integration smoke tests
```

Verified baseline after this commit:

```text
73 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* Full FastAPI app import from `processual_api.main`.
* Health endpoint smoke behavior.
* Global middleware headers.
* Public `/`, `/login`, and `/metrics` routes.
* Protected route anonymous rejection.
* Adapter status smoke path with controlled dependency override.
* `/cgt/govern` controlled smoke path with fake scoring and fake evaluation record.

Purpose:

This confirms the assembled FastAPI application can be exercised as an integrated app without starting `uvicorn`, without Redis, without database access, and without external providers.

---

## TEST-11A — Workflow and Kernel Regression

Commit:

```text
257dc78 TEST-11A add workflow and kernel regression tests
```

Verified baseline after this commit:

```text
79 passed, 6 warnings
compileall: PASS
git diff --check: PASS
```

Coverage:

* `ContinuityEngine`
* `MetricCoefficientMapper`
* `ProcessualCGTKernel`
* `ProcessualMaestroKernel`
* Agent registration
* Duplicate agent rejection
* Agent lookup failure
* Candidate routing by capability and psi
* Agent observation and audit write
* `run_task`
* Workflow creation
* Ready-step calculation
* Manual intervention
* Maestro snapshot
* Workflow execution
* Handoff observation
* Audit normalization
* JSONL audit sink

Purpose:

This protects the orchestration kernel and workflow layer independently from real LLM providers and independently from the real CGT private engine. The test uses fake CGT, fake governor, and fake runtime components to lock the workflow behavior itself.

---

## TEST-12A — CGTLib Public Core Regression

Commit:

```text
579904a TEST-12A add cgtlib public core regression tests
```

Verified baseline after this commit:

```text
85 passed, 6 warnings
compileall: PASS
git diff --check: PASS
git status --short: clean
```

Coverage:

* Top-level `cgtlib` public exports.
* Clear fallback behavior for wrappers requiring the private CGT engine.
* Public validation primitives.
* Public dataclasses and invariants.
* `CGTParameters`
* `PhaseState`
* `StructuralTransitionReport`
* `FateVector`
* `LockState`
* `AftermathState`
* Structural report invariant checks.
* Dataclass serialization through `to_dict`.
* Public manifest generation.

Purpose:

This test documents and protects the public-ready behavior of `cgtlib`. The public package exposes the stable API surface, but private-equation wrappers raise `_FeatureUnavailable` when the private CGT engine is not included. This is expected behavior for the public distribution and should remain explicit.

---

## Final Verified Regression Baseline

Latest verified baseline at the end of TEST-12A:

```text
85 passed, 6 warnings in 2.96s
compileall: PASS
git diff --check: PASS
git status --short: clean
```

The remaining 6 warnings are development/security configuration warnings related to weak or missing deployment values:

```text
JWT_SECRET
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

These warnings are acceptable during local regression testing, but they must be resolved before production deployment.

---

## Final Regression Coverage Summary

The regression suite now protects:

```text
Provider metadata
Adapter registry
Adapter configuration
Adapter status
Adapter readiness
Unified readiness scanner
Dynamic API key verification
API key settings routes
API key revocation
API key usage tracking
API key scopes
API key plans
API key quotas
Settings persistence safety
CGT Governor route boundaries
CGT Governor behavior
Evaluation JSONL store
Governor reports
Security and crypto helpers
Middleware behavior
FastAPI app integration smoke path
Workflow and kernel orchestration
Audit JSONL behavior
CGTLib public package behavior
```

---

## Boundaries Still Outside Core Pytest

The core pytest suite intentionally does not cover:

```text
Real OpenAI calls
Real OpenRouter calls
Real Ollama calls
Real Gemini calls
Real Anthropic calls
Real DeepSeek calls
Live provider latency
Live provider readiness against external services
Production database connectivity
Production Redis connectivity
Browser UI interaction
Google Cloud deployment behavior
```

These must remain separate as operational smoke tests, manual readiness proofs, or deployment-stage checks.

---

---

## TEST-13A — Project Release Regression Guard

Commit:

`42a9634 TEST-13A add project release regression guard`

Purpose:

TEST-13A adds a lightweight release regression guard that verifies the project still contains the minimum expected public-ready structure before moving into deeper production, billing, onboarding, and UI smoke coverage.

Coverage added:

- `docs/reports/API_KEYS_ADAPTERS_REGRESSION_REPORT.md` exists.
- The regression report documents `TEST-05A` through `TEST-12A`.
- The regression report still records the verified `85 passed / 6 warnings` baseline.
- Critical project paths exist.
- A README exists.
- A Python dependency manifest exists.
- `processual_api.main` is importable.
- `processual_kernel` is importable.
- `cgtlib` is importable.
- Static console directories exist.

Validation:

- `tests/test_project_release_regression.py`: `5 passed, 6 warnings`.
- Full baseline after TEST-13A: `90 passed, 6 warnings`.
- `compileall`: PASS.
- `git diff --check`: clean.

Importance:

This test does not replace feature-level regression tests. It acts as a release-structure guard to catch accidental removal of key files, documentation, static console directories, or importable public modules before moving toward production readiness and public release preparation.




## Recommended Next Phase

The safest next phase is not to add new product features immediately, but to complete production readiness:

```text
DOCS-PROD-01 — Production Security Readiness
PROD-ENV-01 — Strong environment configuration
PROVIDER-SMOKE-01 — Manual/live provider smoke scripts outside pytest
DEPLOY-READY-01 — Google Cloud / deployment checklist
UI-SMOKE-01 — Console browser smoke validation
RELEASE-REPORT-01 — Final public-ready release report
```

Recommended first task:

```text
DOCS-PROD-01 — Production Security Readiness
```

This should document and verify the replacement of weak local defaults with production-grade environment variables before any public deployment.
