# EXTERNAL-CONNECTIVITY-16G-R6

## Govern Supervisor Session Storage Overrides

**Status:** implemented and under validation
**Baseline:** `b192157cec784880e51480401f261d11617de591`
**Safety:** local-only, default-deny, no external connectivity

## Purpose

R6 aligns the Admin supervisor-session issue, list, and revoke routes with
the storage path used by supervisor-session authentication.

The fix prevents a key from being issued into one file while
`X-Supervisor-Session-Key` validation reads a different file.

## Defect discovered during manual simulation

Before R6:

- Admin routes wrote session records below `processual_api/data`.
- Authentication honored `PMK_SUPERVISOR_SESSION_KEYS_PATH`.
- Admin route audits wrote below `processual_api/data`.
- The route audit helper ignored `PMK_ADMIN_AUDIT_LOG_PATH`.

A route-issued key could therefore be returned successfully but remain
unavailable to the authentication guard.

## Corrected contracts

| Concern | Override | Preserved fallback |
|---|---|---|
| Session issue/list/revoke | `PMK_SUPERVISOR_SESSION_KEYS_PATH` | `_DATA_DIR/supervisor_session_keys.json` |
| Session authentication | `PMK_SUPERVISOR_SESSION_KEYS_PATH` | existing authentication fallback |
| Admin audit log | `PMK_ADMIN_AUDIT_LOG_PATH` | `_DATA_DIR/admin_audit.jsonl` |
| Integration training events | `PMK_ADMIN_AUDIT_EVENTS_PATH` | existing integration fallback |

The route helpers resolve their variables at call time. Empty or
whitespace-only values preserve the previous `_DATA_DIR` behavior.

`PMK_ADMIN_AUDIT_LOG_PATH` and `PMK_ADMIN_AUDIT_EVENTS_PATH` remain
separate contracts. An isolated simulation exercising both subsystems must
configure both inside its isolated data directory.

## Regression coverage

`tests/test_admin_supervisor_session_route_storage_overrides_16g_r6.py`
proves:

1. Issue writes to `PMK_SUPERVISOR_SESSION_KEYS_PATH`.
2. Authentication resolves the same store.
3. The issued key validates against that store.
4. Storage contains only the key hash, never the raw key.
5. List responses expose neither raw keys nor hashes.
6. Issue audits write to `PMK_ADMIN_AUDIT_LOG_PATH`.
7. Audit events do not contain raw keys.
8. Fallback files are not created when overrides exist.
9. Existing fallbacks remain unchanged without overrides.

The failing-baseline regression redirects `_DATA_DIR` to `tmp_path`, so
reproducing the defect cannot modify repository data.

## Resuming manual simulation

After R6 is committed and pushed:

1. Create a new detached worktree at the R6 commit.
2. Create a new isolated data directory.
3. Configure `PMK_SUPERVISOR_SESSION_KEYS_PATH`.
4. Configure `PMK_ADMIN_AUDIT_LOG_PATH`.
5. Configure `PMK_ADMIN_AUDIT_EVENTS_PATH`.
6. Restore the other isolated simulation store overrides.
7. Start Uvicorn on `127.0.0.1` only.
8. Authenticate without printing the JWT.
9. Prove route and authentication paths are identical.
10. Resume immediately before supervisor-session issuance.

Retain the stopped `b192157` worktree and its evidence until the replacement
worktree passes preflight.

## Guardrails

- `runtime_enabled=false`
- `production_allowed=false`
- `external_http_enabled=false`
- `socket_access_enabled=false`
- `dns_resolution_performed=false`
- `credentials_resolved=false`
- `provider_binding_created=false`
- No provider SDK.
- No external authentication.
- No external sandbox launch.
- No connector dispatcher.
- No production endpoint or certificate.
