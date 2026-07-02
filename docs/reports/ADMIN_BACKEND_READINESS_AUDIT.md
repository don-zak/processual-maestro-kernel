# Admin Backend Readiness Audit

## Phase

ADMIN-REVIEW-01 — Deep admin content, backend readiness, and specialized admin role audit

## Repository State

Branch:

```text
pmk-productization-auth-pricing-usage-cloudrun
```

Baseline commit:

```text
46cd0a1 ADMIN-RUNTIME-01 wire admin runtime and auth bridge
```

This audit starts after the Admin Area runtime was stabilized. It does not reopen already completed work such as static JavaScript asset paths, login token capture, admin auth bridge, Admin Home layout cleanup, or endpoint registry stabilization.

## Audit Rules

The Admin Area must follow these rules:

1. No fake data.
2. No browser request should be sent to an endpoint classified as planned.
3. Missing backend support must be shown as `Not wired yet`.
4. Every card must declare its backend source or planned endpoint.
5. Every write or dangerous action must declare its required admin role and scope.
6. Viewer roles must never see destructive actions as active controls.
7. UI visibility must be mapped to backend authorization, not only front-end hiding.

## Endpoint Status Vocabulary

| Status             | Meaning                                                                       |
| ------------------ | ----------------------------------------------------------------------------- |
| `wired`            | Endpoint exists or is already called intentionally by the Admin Area runtime. |
| `planned`          | Endpoint is planned but must not be called by the browser yet.                |
| `placeholder`      | UI exists but lacks a real backend contract.                                  |
| `read-only-ready`  | UI can safely show backend data but must not mutate state.                    |
| `write-ready`      | UI can perform a backend mutation through a known endpoint and scope.         |
| `dangerous-action` | Action can revoke, delete, disable, reconfigure, or expose sensitive state.   |

## Specialized Admin Roles

| Role             | Purpose                            | Default Access                                                                               |
| ---------------- | ---------------------------------- | -------------------------------------------------------------------------------------------- |
| `owner_admin`    | Full platform owner                | Full read/write access to all Admin Area pages and dangerous actions.                        |
| `ops_admin`      | Operations and provider management | Adapters, Usage Monitor, System Health, provider readiness, operational diagnostics.         |
| `billing_admin`  | Billing and commercial operations  | Clients, applications, plans, subscriptions, billing events, quota profiles.                 |
| `support_admin`  | Client support                     | Read-only clients, applications, reports, and safe bridge-to-client-console actions.         |
| `security_admin` | Security operations                | API keys, key revocation, audit, credential warnings, security settings.                     |
| `viewer_admin`   | Read-only observer                 | Safe read-only dashboard access; no create, revoke, configure, delete, or settings mutation. |

## Scope Naming Proposal

| Scope                   | Intended Use                                                                                                |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| `admin:read`            | General read-only Admin Area access.                                                                        |
| `admin:settings`        | Admin settings read/write access.                                                                           |
| `admin:api_keys:read`   | View API key metadata only.                                                                                 |
| `admin:api_keys:write`  | Create API keys.                                                                                            |
| `admin:api_keys:revoke` | Revoke API keys.                                                                                            |
| `admin:adapters:read`   | View provider and adapter status.                                                                           |
| `admin:adapters:write`  | Configure or test provider connections.                                                                     |
| `admin:usage:read`      | View usage and quota telemetry.                                                                             |
| `admin:clients:read`    | View clients and applications.                                                                              |
| `admin:clients:write`   | Approve, update, or manage client/application state.                                                        |
| `admin:billing:read`    | View plans, subscriptions, and billing events.                                                              |
| `admin:billing:write`   | Change billing or subscription state.                                                                       |
| `admin:health:read`     | View liveness, readiness, storage, and environment health.                                                  |
| `admin:audit:read`      | View security and operational audit records.                                                                |
| `admin:dangerous`       | Perform destructive or high-risk actions. Reserved for `owner_admin` and narrowly scoped specialized roles. |

## Role to Scope Matrix

| Role             | Scopes                                                                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `owner_admin`    | `admin:*`, `admin:dangerous`                                                                                                                    |
| `ops_admin`      | `admin:read`, `admin:adapters:read`, `admin:adapters:write`, `admin:usage:read`, `admin:health:read`                                            |
| `billing_admin`  | `admin:read`, `admin:clients:read`, `admin:clients:write`, `admin:billing:read`, `admin:billing:write`, `admin:usage:read`                      |
| `support_admin`  | `admin:read`, `admin:clients:read`, `admin:usage:read`                                                                                          |
| `security_admin` | `admin:read`, `admin:api_keys:read`, `admin:api_keys:write`, `admin:api_keys:revoke`, `admin:audit:read`, `admin:settings`                      |
| `viewer_admin`   | `admin:read`, `admin:api_keys:read`, `admin:adapters:read`, `admin:usage:read`, `admin:clients:read`, `admin:billing:read`, `admin:health:read` |

## Admin Area Readiness Table

| Page             | Card                     | Endpoint                                            | Current status    | Required backend work                                                                                                  | Required admin role                                                                            | Required scope          | UI action                                   | Next phase        |
| ---------------- | ------------------------ | --------------------------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------- | ----------------- |
| Admin Home       | Operations Summary       | `/health/live`, `/health/ready`, `/adapters/status` | `wired`           | Add richer operational KPIs later                                                                                      | `owner_admin`, `ops_admin`, `viewer_admin`                                                     | `admin:health:read`     | Read-only summary                           | ADMIN-HEALTH-01   |
| Admin Home       | Admin Auth Transport     | `/auth/me`                                          | `wired`           | Expose current role/scopes in auth payload                                                                             | `owner_admin`, `ops_admin`, `billing_admin`, `support_admin`, `security_admin`, `viewer_admin` | `admin:read`            | Read-only session diagnostics               | ADMIN-RBAC-01     |
| Adapters         | Provider Status          | `/adapters/status`                                  | `wired`           | Normalize readiness, last error, latency, model, base_url, auth_mode                                                   | `owner_admin`, `ops_admin`, `viewer_admin`                                                     | `admin:adapters:read`   | Status table                                | ADMIN-ADAPTERS-02 |
| Adapters         | Configure Provider       | `/adapters/configure`                               | `wired candidate` | Verify request schema and required admin scope                                                                         | `owner_admin`, `ops_admin`                                                                     | `admin:adapters:write`  | Configure provider                          | ADMIN-ADAPTERS-02 |
| Adapters         | Test Provider Connection | `/adapters/test`                                    | `wired candidate` | Verify response schema and failure handling                                                                            | `owner_admin`, `ops_admin`                                                                     | `admin:adapters:write`  | Test connection                             | ADMIN-ADAPTERS-02 |
| API Keys         | API Key List             | `/settings/api-keys`                                | `wired`           | Confirm list schema includes key_id, category, role, scopes, status, usage_count, last_used_at, created_at, revoked_at | `owner_admin`, `security_admin`, `viewer_admin`                                                | `admin:api_keys:read`   | Read metadata only                          | ADMIN-APIKEYS-02  |
| API Keys         | Create API Key           | `/settings/api-keys`                                | `wired`           | Harden category, role, scopes, plan/quota profile payload                                                              | `owner_admin`, `security_admin`                                                                | `admin:api_keys:write`  | Create key; show raw key only once          | ADMIN-APIKEYS-02  |
| API Keys         | Revoke API Key           | `/settings/api-keys/{key_id}`                       | `wired candidate` | Confirm DELETE route and non-raw-key revocation flow                                                                   | `owner_admin`, `security_admin`                                                                | `admin:api_keys:revoke` | Dangerous revoke action                     | ADMIN-APIKEYS-02  |
| Clients          | Applications             | `/applications`                                     | `wired`           | Confirm application list schema and approval state                                                                     | `owner_admin`, `billing_admin`, `support_admin`, `viewer_admin`                                | `admin:clients:read`    | Read applications                           | ADMIN-CLIENTS-01  |
| Clients          | Plans                    | `/billing/plans`                                    | `planned`         | Build plans endpoint before browser calls it                                                                           | `owner_admin`, `billing_admin`, `viewer_admin`                                                 | `admin:billing:read`    | Show Not wired yet                          | ADMIN-CLIENTS-01  |
| Clients          | Subscriptions            | `/billing/subscriptions`                            | `planned`         | Build subscriptions endpoint before browser calls it                                                                   | `owner_admin`, `billing_admin`, `viewer_admin`                                                 | `admin:billing:read`    | Show Not wired yet                          | ADMIN-CLIENTS-01  |
| Clients          | Billing Events           | `/billing/events`                                   | `planned`         | Build billing events endpoint before browser calls it                                                                  | `owner_admin`, `billing_admin`                                                                 | `admin:billing:read`    | Show Not wired yet                          | ADMIN-CLIENTS-01  |
| Usage Monitor    | Usage Logs               | `/settings/usage-logs`                              | `planned`         | Build sanitized usage logs endpoint                                                                                    | `owner_admin`, `ops_admin`, `billing_admin`, `support_admin`, `viewer_admin`                   | `admin:usage:read`      | Show Not wired yet                          | ADMIN-USAGE-01    |
| Usage Monitor    | Usage Summary            | `/settings/usage-summary`                           | `planned`         | Build aggregate summary endpoint                                                                                       | `owner_admin`, `ops_admin`, `billing_admin`, `viewer_admin`                                    | `admin:usage:read`      | Show Not wired yet                          | ADMIN-USAGE-01    |
| Program Progress | Progress Overview        | none confirmed                                      | `placeholder`     | Define real backend contract or keep static documentation only                                                         | `owner_admin`, `viewer_admin`                                                                  | `admin:read`            | Read-only placeholder until contract exists | ADMIN-REVIEW-02   |
| System Health    | Live Check               | `/health/live`                                      | `wired`           | None for basic liveness                                                                                                | `owner_admin`, `ops_admin`, `viewer_admin`                                                     | `admin:health:read`     | Read-only health card                       | ADMIN-HEALTH-01   |
| System Health    | Ready Check              | `/health/ready`                                     | `wired`           | Extend readiness details later                                                                                         | `owner_admin`, `ops_admin`, `viewer_admin`                                                     | `admin:health:read`     | Read-only readiness card                    | ADMIN-HEALTH-01   |
| System Health    | Provider Readiness       | `/adapters/status`                                  | `wired`           | Include provider readiness and last error                                                                              | `owner_admin`, `ops_admin`, `viewer_admin`                                                     | `admin:adapters:read`   | Read-only provider health                   | ADMIN-HEALTH-01   |
| System Settings  | Settings Overview        | none confirmed                                      | `placeholder`     | Identify real settings endpoints before adding controls                                                                | `owner_admin`, `security_admin`                                                                | `admin:settings`        | No write controls until endpoint exists     | ADMIN-RBAC-01     |

## UI Permission Behavior

| Action class      | Allowed roles                                   | UI behavior for unauthorized roles                                      |
| ----------------- | ----------------------------------------------- | ----------------------------------------------------------------------- |
| Read-only cards   | Any role with matching read scope               | Visible if safe; otherwise hidden.                                      |
| Create key        | `owner_admin`, `security_admin`                 | Hide or disable with clear permission label.                            |
| Revoke key        | `owner_admin`, `security_admin`                 | Hide for unauthorized roles; require confirmation for authorized roles. |
| Configure adapter | `owner_admin`, `ops_admin`                      | Hide or disable for non-ops roles.                                      |
| Test adapter      | `owner_admin`, `ops_admin`                      | Disable for non-ops roles.                                              |
| Billing mutation  | `owner_admin`, `billing_admin`                  | Hide until backend endpoint and scope exist.                            |
| Settings mutation | `owner_admin`, `security_admin`                 | Hide until backend endpoint and scope exist.                            |
| Dangerous action  | `owner_admin`, narrowly scoped specialized role | Hide by default; require confirmation and audit trail.                  |

## Backend Readiness Findings

1. The current Admin Area has a working runtime foundation.
2. The endpoint registry should remain the source of truth for wired versus planned endpoints.
3. Planned endpoints must remain non-networked from the browser until implemented.
4. API Keys and Adapters are the highest-value next hardening targets.
5. RBAC should be designed now but implemented in a separate phase to avoid mixing UI audit with authorization refactor.
6. The `/auth/me` response should eventually expose current admin role and scopes.
7. UI hiding is not security. Backend endpoints must enforce scopes.

## Recommended Next Phases

| Phase             | Purpose                                                                          |
| ----------------- | -------------------------------------------------------------------------------- |
| ADMIN-APIKEYS-02  | Harden API key lifecycle: create, list, revoke, metadata, scopes, quota profile. |
| ADMIN-ADAPTERS-02 | Harden adapter admin operations: configure, test, status, readiness.             |
| ADMIN-USAGE-01    | Build usage summary and logs backend wiring.                                     |
| ADMIN-CLIENTS-01  | Build clients, applications, plans, subscriptions, and billing admin view.       |
| ADMIN-HEALTH-01   | Deepen system health cards and storage/environment readiness.                    |
| ADMIN-RBAC-01     | Implement scoped admin roles in backend and UI.                                  |

## Commit Scope for ADMIN-REVIEW-01

This phase should only add the audit report and regression coverage for the audit content.

It should not implement RBAC enforcement yet.

It should not add fake UI data.

It should not call planned endpoints from the browser.

It should not modify production authorization behavior until ADMIN-RBAC-01.
