# API Key Profiles Admin Provisioning

## Phase

ADMIN-APIKEYS-02A — Document admin API key profiles and billing access policy

## Purpose

This report defines the governed API key profile matrix before changing backend
schema or Admin Area UI behavior.

The goal is to let authorized administrators provision all required API key
types for Processual Maestro without weakening the normal authentication model.

Some parties may need programmatic access without using the browser login chain.
That access must be handled through scoped API keys, not by exposing stored raw
keys, bypassing authorization, or sharing admin credentials.
This policy is governed scoped access provisioning.

## Current Route Baseline

The existing API key route surface already includes:

| Method | Route | Purpose |
|---|---|---|
| GET | `/settings/api-keys` | List visible API key metadata. |
| POST | `/settings/api-keys` | Create a new dynamic API key. |
| PATCH | `/settings/api-keys/{key_id}/plan` | Update key plan binding. |
| PATCH | `/settings/api-keys/{key_id}/quota` | Update key quota override. |
| DELETE | `/settings/api-keys/{key_id}` | Soft revoke an API key. |

ADMIN-APIKEYS-02A does not add new routes.

## Security Rules

1. No raw API key is stored.
2. No raw API key is recoverable after creation.
3. Raw API key material may only be shown once in the create response.
4. API key lists must only show metadata such as id, prefix, label, role,
   scopes, quota, status, and timestamps.
5. Revoke must use `key_id`, not a raw key.
6. Every key must have a category, role, scope set, quota profile, and owner.
7. High-risk keys must have an expiry policy.
8. Programmatic access without UI login is allowed only through governed scoped
   keys.
9. UI hiding is not security. Backend authorization must enforce all scopes.
10. Billing state must be able to restrict, downgrade, or suspend key access.

## Admin Roles

| Role | Purpose |
|---|---|
| `owner_admin` | Full platform owner with all provisioning rights. |
| `security_admin` | Security operator for API keys, revocation, audit, and settings. |
| `ops_admin` | Operations administrator for adapters, usage, health, and service keys. |
| `billing_admin` | Billing operator for clients, plans, subscriptions, and quotas. |
| `support_admin` | Support operator with safe read-only client and usage visibility. |
| `viewer_admin` | Read-only observer with no mutation rights. |

## Admin Scopes

| Scope | Meaning |
|---|---|
| `admin:read` | General Admin Area read access. |
| `admin:settings` | Settings administration. |
| `admin:api_keys:read` | View API key metadata. |
| `admin:api_keys:write` | Create governed API keys. |
| `admin:api_keys:revoke` | Revoke API keys. |
| `admin:adapters:read` | View adapter status. |
| `admin:adapters:write` | Configure or test adapters. |
| `admin:usage:read` | View usage and quota telemetry. |
| `admin:clients:read` | View clients and applications. |
| `admin:clients:write` | Manage client/application state. |
| `admin:billing:read` | View billing plans, subscriptions, and events. |
| `admin:billing:write` | Mutate billing-linked state. |
| `admin:health:read` | View system health and readiness. |
| `admin:audit:read` | View audit events. |
| `admin:dangerous` | Perform high-risk administrative actions. |

## API Key Categories

| Category | Purpose | Login UI required? | Risk |
|---|---|---:|---|
| `client_api` | Normal client API access. | No | Medium |
| `pilot_client` | Temporary pilot or demo access. | No | Medium |
| `external_partner` | External technical partner access. | No | High |
| `service_integration` | Service-to-service integration access. | No | High |
| `billing_service` | Billing sync or payment integration service access. | No | High |
| `support_viewer` | Support read-only access. | Optional | Low |
| `ops_admin` | Operations administrator API access. | Optional | High |
| `billing_admin` | Billing administrator API access. | Optional | High |
| `security_admin` | Security administrator API access. | Optional | Critical |
| `owner_admin` | Owner-level administrative API access. | Optional | Critical |
| `emergency_bootstrap` | Short-lived emergency access. | No | Critical |

## Profile Matrix

| Category | Default role | Default scopes | Creator roles | Expiry policy |
|---|---|---|---|---|
| `client_api` | `client` | `read:health`, `read:governor`, `run:analyze`, `run:govern`, `read:reports`, `create:reports` | `owner_admin`, `security_admin`, `billing_admin` | Optional, plan-driven |
| `pilot_client` | `client` | `read:health`, `read:governor`, `run:analyze`, `run:govern`, `read:reports` | `owner_admin`, `security_admin`, `billing_admin` | Required or strongly recommended |
| `external_partner` | `partner` | Minimal explicit scopes only | `owner_admin`, `security_admin` | Required |
| `service_integration` | `service` | Explicit service scopes only | `owner_admin`, `security_admin`, `ops_admin` | Required for non-internal services |
| `billing_service` | `service` | `admin:billing:read`, `admin:billing:write` | `owner_admin`, `security_admin` | Required |
| `support_viewer` | `support_admin` | `admin:read`, `admin:clients:read`, `admin:usage:read` | `owner_admin`, `security_admin` | Optional |
| `ops_admin` | `ops_admin` | `admin:read`, `admin:adapters:read`, `admin:adapters:write`, `admin:usage:read`, `admin:health:read` | `owner_admin`, `security_admin` | Optional |
| `billing_admin` | `billing_admin` | `admin:read`, `admin:clients:read`, `admin:clients:write`, `admin:billing:read`, `admin:billing:write`, `admin:usage:read` | `owner_admin`, `security_admin` | Optional |
| `security_admin` | `security_admin` | `admin:read`, `admin:settings`, `admin:api_keys:read`, `admin:api_keys:write`, `admin:api_keys:revoke`, `admin:audit:read` | `owner_admin` | Optional, high audit |
| `owner_admin` | `owner_admin` | `admin:*`, `admin:dangerous` | `owner_admin` | Optional, high audit |
| `emergency_bootstrap` | `owner_admin` | Minimal emergency scopes only | `owner_admin` | Required and short-lived |

## Programmatic Access Without Browser Login

Programmatic access without the normal login chain is allowed only for the
following categories:

| Category | Allowed? | Conditions |
|---|---:|---|
| `client_api` | Yes | Must be scoped, quota-bound, and client-linked. |
| `pilot_client` | Yes | Must be limited and preferably expiring. |
| `external_partner` | Yes | Must be narrowly scoped and expiring. |
| `service_integration` | Yes | Must be service-purpose scoped. |
| `billing_service` | Yes | Must be restricted to billing sync operations. |
| `emergency_bootstrap` | Yes | Must be short-lived and audited. |
| `support_viewer` | Limited | Read-only only. |
| `ops_admin` | Limited | Operational scopes only. |
| `billing_admin` | Limited | Billing scopes only. |
| `security_admin` | Limited | Security scopes only. |
| `owner_admin` | Limited | Owner-only and audited. |

This is not an authentication bypass. It is governed scoped access
provisioning.

## Billing and Lemon Squeezy Readiness

Lemon Squeezy integration should become the billing authority for:

1. Checkout creation.
2. Subscription state.
3. Customer portal access.
4. Billing events.
5. Plan-to-quota mapping.
6. Subscription-to-key access policy.

Expected environment variables:

| Variable | Purpose |
|---|---|
| `LEMONSQUEEZY_API_KEY` | Server-side Lemon Squeezy API token. |
| `LEMONSQUEEZY_STORE_ID` | Store identifier. |
| `LEMONSQUEEZY_WEBHOOK_SECRET` | Webhook signing secret. |
| `LEMONSQUEEZY_STARTER_VARIANT_ID` | Starter plan variant. |
| `LEMONSQUEEZY_PRO_VARIANT_ID` | Pro plan variant. |
| `LEMONSQUEEZY_BUSINESS_VARIANT_ID` | Business plan variant. |
| `LEMONSQUEEZY_SUCCESS_URL` | Checkout success redirect. |
| `LEMONSQUEEZY_CANCEL_URL` | Checkout cancellation redirect. |

No real Lemon Squeezy secret may be committed to Git.

## Billing to API Key Policy

| Billing state | API key policy |
|---|---|
| `trialing` | Allow pilot or limited client keys. |
| `active` | Allow plan-bound client keys. |
| `past_due` | Restrict new key creation and warn admin. |
| `cancelled` | Prevent new client keys unless owner override exists. |
| `expired` | Suspend or restrict client keys after grace policy. |
| `refunded` | Flag for manual security review. |
| `disputed` | Flag for owner/security review. |

## Required Backend Schema Direction

Future backend hardening should extend API key creation payloads toward:

| Field | Purpose |
|---|---|
| `category` | API key profile category. |
| `role` | Runtime role attached to the key. |
| `scopes` | Explicit allowed scopes. |
| `plan_id` | Plan binding. |
| `quota_limit_override` | Optional quota override. |
| `expires_at` | Optional or required expiry timestamp. |
| `client_id` | Linked client identity. |
| `user_id` | Linked user identity. |
| `label` | Human-readable admin label. |
| `purpose` | Why the key was created. |
| `issued_to` | Person, client, service, or partner receiving the key. |
| `created_by_admin_role` | Admin role that created the key. |

## Required Admin UI Direction

The Admin API Keys page should eventually include:

1. Category selector.
2. Role selector.
3. Scope checklist.
4. Plan/quota profile selector.
5. Expiry field.
6. Purpose field.
7. Issued-to field.
8. Generate button.
9. One-time raw key display box.
10. Copy button.
11. Raw key warning.
12. Metadata table.
13. Refresh button.
14. Revoke button.
15. Permission labels for read-only roles.

## Key Metadata Table

The table should display:

| Field |
|---|
| `key_id` |
| `prefix` |
| `label` |
| `category` |
| `role` |
| `scopes` |
| `client_id` |
| `user_id` |
| `plan_id` |
| `quota_scope` |
| `quota_limit` |
| `quota_used` |
| `status` |
| `usage_count` |
| `last_used_at` |
| `created_at` |
| `expires_at` |
| `revoked_at` |

The table must not display raw API key material.

## Phase Boundaries

ADMIN-APIKEYS-02A should only add this report and regression coverage.

It should not modify backend schemas.

It should not modify JavaScript.

It should not implement Lemon Squeezy API calls.

It should not create the lifecycle UI yet.

It should not create `tests/test_admin_api_key_lifecycle_regression.py` yet.

## Next Phases

| Phase | Purpose |
|---|---|
| ADMIN-APIKEYS-02B | Harden backend create/list/revoke schema for profiles. |
| ADMIN-APIKEYS-02C | Build Admin UI profile provisioning and lifecycle controls. |
| BILLING-LEMON-01 | Add Lemon Squeezy configuration readiness. |
| BILLING-LEMON-02 | Add checkout and customer portal backend routes. |
| BILLING-LEMON-03 | Add Lemon Squeezy webhook verification and subscription sync. |
| ADMIN-BILLING-01 | Add Admin billing/subscriptions view. |