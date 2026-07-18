# Admin / Supervisor Workspace Inventory

Phase:

ADMIN-SUPERVISOR-WORKSPACE-INVENTORY-01 inventory current admin/supervisor surfaces

## Purpose

This document inventories the current Admin and Supervisor workspace after supervisor session keys, RBAC, live refresh, and browser-flow proof.

No extra hardening phase is planned here.

The supervisor workspace is treated as a controlled operational environment. The next direction is operational visibility: counters, summaries, audit views, and statistics.

## Admin Home

Admin Home is the top-level operational landing area.

Current content:
- admin operations overview
- protected admin session status
- Supervisor Session card
- links back to Client Console and admin login/logout flow

## Supervisor Session

The Supervisor Session card shows:
- supervisor session status
- supervisor level
- backend scopes
- clear supervisor session key action
- legacy-compatible fallback when no supervisor session key is present

Backend enforcement remains authoritative.

The UI is only a reflection layer. It is not the security boundary.

## API Keys

The API Keys page hosts admin key lifecycle controls.

Current content:
- generate standard admin/API keys
- list existing keys
- key category presets
- service integration key presets
- security/admin/billing/ops key categories

Future metric:
- API key lifecycle summary

## Supervisor Session Keys

Supervisor Session Keys are managed inside the API Keys page.

Current content:
- issue review_supervisor keys
- issue operations_supervisor keys
- list safe metadata
- revoke keys
- display one-time raw key only at issue time
- use key for this browser session
- clear key from this browser session
- store active browser key under pmk_supervisor_session_key
- dispatch pmk-supervisor-session-key-updated after use or clear

Security boundary:
- Do not display raw supervisor session keys outside one-time issue output.
- Do not display raw supervisor session keys in lists.
- Do not display raw supervisor session keys in audit.
- Do not display key_hash.

## Client Requests

Client Requests are the main supervisor work queue.

Current content:
- request inbox/detail
- Mark Reviewed
- Approve
- Reject
- Complete
- Generate Draft
- Save Draft
- Send Response
- client-visible response timeline
- RBAC button reflection for review_supervisor and operations_supervisor

Useful operational metrics:
- requests by status
- pending
- reviewed
- approved
- rejected
- completed
- draft saved
- response sent

## Provider

Provider controls are currently represented through provider configuration and adapter connection surfaces.

Potential future summary:
- configured provider status
- last provider test result
- provider readiness
- missing configuration warnings

Provider secrets must not be exposed in summaries.

## Adapters

Adapters are part of the Admin operational surface.

Current content:
- provider list
- configured/unconfigured status
- configure provider
- test connection

Potential future summary:
- configured adapters
- enabled adapters
- adapters requiring attention

## Audit

Audit currently exists as backend event recording.

Known supervisor/admin event families:
- supervisor session key issued
- supervisor session key revoked
- supervisor session key denied
- admin client request status updated
- admin client request status denied
- supervisor response draft saved
- supervisor response draft denied
- supervisor response sent
- supervisor response denied
- supervisor response already sent

Future tool:
- supervisor audit summary

Safe fields:
- action
- actor
- actor_level
- target_type
- target_id
- result
- reason
- created_at

Do not display raw supervisor session keys.
Do not display key_hash.
Do not display provider_secret.
Do not display encrypted_key.
Do not display authorization, cookie, or jwt values.

## Health

System Health is the operational readiness surface.

Potential future summary:
- health/live
- health/ready
- provider readiness
- telemetry state
- usage logging state
- audit storage
- backup state
- production warning status

## Billing

Billing and usage are relevant to Admin because of usage ledger and BYOK pricing work.

Potential future summary:
- usage ledger status
- billable usage summary
- client plan status
- quota status
- billing sync status

## Recommended next tools

Recommended order:
1. Admin supervisor overview counters
2. Client requests by status
3. Recent supervisor audit summary
4. API key lifecycle summary
5. Provider and adapter health summary
6. Usage and billing summary

## First recommended implementation

ADMIN-SUPERVISOR-STATS-01 add supervisor workspace overview counters

Suggested first UI:
- Pending requests
- Reviewed requests
- Approved requests
- Rejected requests
- Completed requests
- Drafts saved
- Responses sent

Rules:
- visibility only
- statistics are not permission checks
- Backend enforcement remains authoritative
- Do not display raw supervisor session keys
- Do not display key_hash
- Do not display provider_secret
- Do not display encrypted_key
