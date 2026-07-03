# Maestro Client and Supervisor Content Map

## Phase

CLIENT-CONTENT-01 document client supervisor content map

## Purpose

This document fixes the official content boundary between the client console and the supervisor admin area before adding new UI.

The goal is to preserve the existing Processual Maestro UI/UX while preparing the next productization steps for usage visibility, quota explanation, BYOK provider connections, support requests, and supervisor review.

This phase is documentation-only. It does not add UI, CSS, JavaScript, backend routes, checkout, OAuth, activation endpoints, or billing flows.

## Current technical foundation

The current implementation already provides the backend foundation for usage visibility:

* `summarize_usage_logs()` summarizes usage ledger events.
* `usage_logs.jsonl` is the ledger source.
* `GET /settings/usage-summary` exposes the client usage summary endpoint.
* The ledger records Maestro usage units, quota metadata, endpoint class metadata, and rejection metadata.
* The system follows BYOK policy.
* `provider_cost_included=false` remains a required commercial truth.
* `quota_rejected` identifies quota rejection events.
* Rejected requests must not be presented as successful consumption.

## Client console content map

The client console must show only the current client's own account, usage, keys, provider connections, and support path.

The client page is not admin page.

### 1. Identity

Purpose:

* Show the client account identity.
* Help the client understand which account or API profile is active.
* Avoid exposing supervisor-only metadata.

Suggested content:

* client_id
* account label
* active role
* profile status

### 2. Plan & Usage

Purpose:

* Show the active plan.
* Show plan quota in Maestro units.
* Show current usage in Maestro units.
* Explain remaining quota clearly.

Suggested content:

* plan_id
* quota_limit
* quota_used
* quota_remaining
* total_units
* successful_units
* rejected_units

### 3. API Keys

Purpose:

* Let the client understand and manage client-owned API keys.
* Never expose raw API keys after creation.

Suggested content:

* key_id
* key prefix only
* status
* scopes
* last_used_at
* usage_count
* revoke action

Rules:

* Do not display raw API key values.
* Do not expose supervisor-only key controls.
* Do not mix client key management with admin key supervision.

### 4. Provider Connections

Purpose:

* Explain and manage customer-owned provider connections.
* Preserve the BYOK commercial model.

Suggested content:

* provider status
* provider kind
* connection readiness
* BYOK explanation
* `provider_cost_included=false`

Rules:

* Maestro does not sell provider tokens.
* Maestro sells governance and Maestro usage units.
* Provider costs belong to the client provider account.

### 5. Usage & Quotas

Purpose:

* Give the client a small and clear summary of usage and quota health.
* Use the existing endpoint `GET /settings/usage-summary`.

Suggested content:

* plan_id
* quota_limit
* quota_used
* quota_remaining
* total_events
* successful_requests
* rejected_requests
* total_units
* successful_units
* rejected_units
* by_endpoint_class
* by_status_code
* top_endpoints
* latest_events
* avg_latency_ms

Rules:

* Rejected requests must be visible as rejected.
* Rejected requests must not look like successful usage.
* Quota rejection must explain `quota_rejected`.
* Endpoint classes must stay tied to Maestro usage units.

### 6. Requests / Billing

Purpose:

* Let the client request a plan change, overage discussion, enterprise onboarding, or billing support.
* Do not add checkout yet.

Suggested content:

* request upgrade
* request enterprise
* request overage
* request onboarding
* request quota review

Rules:

* No checkout in this phase.
* No payment flow in this phase.
* No subscription activation endpoint in this phase.

### 7. Support

Purpose:

* Give the client a clear path to ask for help using account and ledger context.

Suggested content:

* support request
* quota rejection help
* provider connection help
* onboarding help
* enterprise follow-up request

## Supervisor admin content map

The supervisor admin area must support monitoring, diagnosis, and customer follow-up.

Supervisor content must not be placed inside the client console.

### 1. Client Overview

Purpose:

* Give the supervisor a high-level view of clients and their current usage state.

Suggested content:

* client_id
* plan_id
* quota_limit
* quota_used
* quota_remaining
* last_used_at
* client status

### 2. API Key Supervision

Purpose:

* Help the supervisor review API key lifecycle and status without exposing raw keys.

Suggested content:

* client_id
* key_id
* key prefix only
* status
* scopes
* last_used_at
* usage_count
* revoked state

Rules:

* Do not display raw API keys.
* Do not leak client secrets.
* Do not mix admin supervision with client self-service flows.

### 3. Usage Ledger Review

Purpose:

* Let the supervisor review ledger-backed usage details.

Suggested content:

* total_events
* successful_requests
* rejected_requests
* total_units
* successful_units
* rejected_units
* by_endpoint_class
* by_status_code
* top_endpoints
* latest_events
* avg_latency_ms

Technical source:

* `usage_logs.jsonl`
* `summarize_usage_logs()`
* `GET /settings/usage-summary` for client-facing summary behavior

### 4. Quota & Plan Control

Purpose:

* Help the supervisor understand quota state and plan alignment.

Suggested content:

* plan_id
* quota_scope
* quota_limit
* quota_used
* quota_requested
* quota_remaining
* quota_before
* quota_after

Rules:

* Quota control belongs in supervisor flows.
* Client UI should explain quota status, not expose supervisor controls.

### 5. Support Intelligence

Purpose:

* Help the supervisor answer support questions using ledger evidence.

Suggested content:

* quota_rejected
* status_code
* endpoint_class
* units_charged
* latest_events
* client support context

Rules:

* A 429 quota rejection must remain audit-visible.
* The support view should help explain why a request failed.

### 6. Enterprise Follow-up

Purpose:

* Help the supervisor identify enterprise usage, quota pressure, and upgrade opportunities.

Suggested content:

* enterprise plan candidates
* high usage clients
* repeated quota rejection
* overage discussion candidates
* onboarding status

Rules:

* No checkout in this phase.
* No automatic billing activation in this phase.
* Enterprise follow-up must stay supervisor-owned.

## UI/UX preservation rules

The next UI phases must preserve the existing interface.

Required rules:

* preserve existing UI
* no redesign
* no CSS unless explicitly required
* reuse existing classes
* reuse existing page structure
* no new navigation unless necessary
* no visual identity changes
* no color changes
* no spacing redesign
* no broad refactor
* client page is not admin page

Existing reusable classes should be preferred:

* card
* settings-grid
* inp-group
* mono-block
* btn
* sec-hdr
* nav-btn
* data-page

## Explicit non-goals

This phase does not implement:

* client usage summary card
* supervisor usage overview
* checkout
* payment flow
* Google OAuth
* activation endpoint
* new CSS
* UI redesign
* raw API key display
* provider token resale

## Next phases

### CLIENT-USAGE-01C

Add a small client Usage & Quotas card using the existing console UI/UX.

Expected source:

* `GET /settings/usage-summary`

Expected fields:

* plan_id
* quota_used
* quota_remaining
* total_units
* rejected_requests
* latest status

Rules:

* No new CSS.
* No redesign.
* No admin content in the client page.

### ADMIN-USAGE-01A

Add supervisor usage overview using the existing admin UI/UX.

Expected content:

* client_id
* plan_id
* total_units
* successful_units
* rejected_requests
* quota_remaining
* by_endpoint_class
* by_status_code
* latest_events

Rules:

* No raw API keys.
* No client secrets.
* No client/admin route mixing.

## Acceptance markers

This document intentionally preserves these implementation markers for regression tests:

* Identity
* Plan & Usage
* API Keys
* Provider Connections
* Usage & Quotas
* Requests / Billing
* Support
* Client Overview
* API Key Supervision
* Usage Ledger Review
* Quota & Plan Control
* Support Intelligence
* Enterprise Follow-up
* `/settings/usage-summary`
* `summarize_usage_logs()`
* `usage_logs.jsonl`
* BYOK
* `provider_cost_included=false`
* `quota_rejected`
* preserve existing UI
* no redesign
* no CSS unless explicitly required
* reuse existing classes
* client page is not admin page
