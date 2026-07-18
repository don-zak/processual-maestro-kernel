# INTEGRATION UI/UX AND BACKEND CONTRACT 13D

Generated: 2026-07-09T12:31:20.179806+00:00

## Purpose

13D freezes the integration surfaces before further fixes. It maps UI panels to scripts, backend routes, auth/scope contracts, payload/state expectations, tests, and browser proofs.

No functional patch is allowed before the contract gates identify the exact failing boundary.

## Current Evidence Snapshot

| Check | Value |
|---|---|
| `13b_html_version` | `adminpilot13b-supervisor-map-r6` |
| `13b_js_version` | `adminpilot13b-isolated-recovery` |
| `13b_html_version_claim_inside_js` | `false` |
| `13b_js_has_supervisor_session_reader` | `false` |
| `13b_js_has_supervisor_scope_reader` | `false` |
| `13b_js_has_admin_session_header` | `true` |
| `13b_js_has_admin_scopes_header` | `false` |
| `13b_js_has_write_scope_marker` | `false` |
| `13b_js_has_error_formatter` | `true` |
| `main_py_has_integration_tasks_routes` | `true` |
| `main_py_reads_scope_headers` | `true` |
| `api_keys_backend_authoritative_text` | `true` |
| `settings_usage_summary_binding` | `true` |

## Surface Contract Matrix

| Surface | Script | Backend route family | Contract | Phase |
|---|---|---|---|---|
| Admin API Keys | admin_api_keys.js | /settings/admin/api-keys or existing admin key routes | Backend authoritative scopes; no raw secrets in tables | 13D Phase 1 |
| 13B Activation Permission License | admin_integration_pilot_controls_13b.js | /settings/admin/integration-tasks + activation-permission-key | Supervisor session; backend-derived scopes | 13D Phase 2 |
| 13B Pilot Tracking | admin_integration_pilot_controls_13b.js | /settings/admin/integration-tasks/{task_id}/suspend|resume|revoke|cancel | State transitions must be proven | 13D Phase 2 |
| Settings Integration Readiness | settings.js | /settings/client/usage-summary + claim/status/readiness routes | Plan/allowance/backend-bound, no mock state | 13D Phase 3 |

## Backend Routes Detected In main.py

| Method | Route |
|---|---|
| `GET` | `/settings/admin/integration-readiness-tracking` |
| `POST` | `/settings/admin/integration-readiness-tracking/cases` |
| `POST` | `/settings/admin/integration-readiness-tracking/cases/{case_id:path}/items` |
| `GET` | `/settings/admin/integration-readiness-tracking/cases` |
| `GET` | `/settings/admin/integration-readiness-tracking/case-detail` |
| `GET` | `/settings/admin/integration-readiness-tracking/cases/{case_id:path}` |
| `POST` | `/settings/admin/integration-readiness-tracking/case-item-action` |
| `GET` | `/settings/admin/integration-readiness-operator-package` |
| `GET` | `/settings/admin/integration-readiness-operator-package/export` |
| `POST` | `/settings/admin/integration-claim-keys` |
| `GET` | `/settings/admin/integration-claim-keys` |
| `POST` | `/settings/admin/integration-claim-keys/{claim_key_id}/revoke` |
| `POST` | `/settings/client/integration-claim-keys/redeem` |
| `GET` | `/settings/client/integration-onboarding/status` |
| `GET` | `/settings/admin/integration-tasks` |
| `POST` | `/settings/admin/integration-tasks` |
| `POST` | `/settings/admin/integration-tasks/{task_id}/suspend` |
| `POST` | `/settings/admin/integration-tasks/{task_id}/resume` |
| `POST` | `/settings/admin/integration-tasks/{task_id}/revoke` |
| `POST` | `/settings/admin/integration-tasks/{task_id}/cancel` |
| `POST` | `/settings/admin/integration-tasks/{task_id}/activation-permission-key` |

## Frontend Route References Detected

- `/settings/admin/integration-tasks`
- `/settings/client/integration-claim-keys/redeem`
- `/settings/client/integration-onboarding/status`
- `/settings/api-keys/${keyId}`

## 13D Gates

1. Version truth: HTML cache-buster must match a real marker inside the loaded JS.
2. No frontend-auth invention: the frontend may pass a supervisor session, but backend must derive or verify scopes authoritatively.
3. API Keys UX: tables must be framed, buttons readable, raw secrets absent from safe metadata lists, and errors formatted.
4. Integration readiness backend: every create/control action must have a route, auth contract, payload contract, state mutation, and test.
5. Settings readiness: every readiness/claim/usage card must bind to backend state, not local mock state.
6. Quantity/plan limits: task or activation limits must come from an explicit backend contract, not an inferred UI number.
7. Browser proof is mandatory before commit.

## Known Current Blockers

- 13B version mismatch: HTML uses `adminpilot13b-supervisor-map-r6` but JS declares `adminpilot13b-isolated-recovery`.
- 13B scope mismatch: backend reads supervisor scope headers, but frontend JS does not send `X-Admin-Supervisor-Scopes`.

## Allowed Next Patch Types

- One UI-only patch.
- Or one backend-only patch.
- Or one test-only patch.

No mixed UI + backend + auth + CSS patch is allowed in a single step.
