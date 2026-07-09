# Integration Onboarding 13B — Pilot Terms, Revocation Controls, and Activation Permission Keys

Status: `draft_review`

## Purpose

13B adds supervisor controls for integration pilot tasks and adds a safe activation permission key extraction flow from the Admin API Keys workspace.

## Key rule

```text
Activation Permission Key is not a runtime connector key.
Activation Permission Key is not a production key.
Activation Permission Key does not enable external HTTP.
Activation Permission Key does not expose raw secrets.
```

## Supervisor controls

```text
suspend
resume
revoke
cancel
```

## Routes

```text
GET  /settings/admin/integration-tasks
POST /settings/admin/integration-tasks
POST /settings/admin/integration-tasks/{task_id}/suspend
POST /settings/admin/integration-tasks/{task_id}/resume
POST /settings/admin/integration-tasks/{task_id}/revoke
POST /settings/admin/integration-tasks/{task_id}/cancel
POST /settings/admin/integration-tasks/{task_id}/activation-permission-key
```

## Activation permission key

The activation permission key is extracted from the Admin API Keys workspace.
It is visible once in the response/UI. Only a hash is stored. List views display a masked value only.

## Safety behavior

```text
suspended = temporarily disables the pilot task
resumed = returns task to supervisor review
revoked = revokes the task and marks integration key revoked
cancelled = cancels the task and keeps all grants disabled
```


## Admin API Keys projection

```text
key_family = activation_permission_key
format = iapk_<id>.<visible-once-secret>
masked_list_value = iapk_****************
runtime_api_key = false
production_key = false
```

The Admin API Keys workspace shows this as a permission-key family for supervisor workflow visibility only.
It must not be treated as a runtime API key or production credential.
The actual Admin API Keys list must also render a shadow API key item sourced from pilot tasks:

```text
data-admin-api-key-shadow-activation-permission = true
data-admin-api-key-list-item = activation_permission_key
masked_value = iapk_****************
runtime = false
production = false
external_http = false
secret_visible = false
```

This shadow item is a UI/admin projection only. It does not create a provider credential or runtime connector credential.

The Admin API Keys card must also render a clearly visible catalog item:

```text
data-admin-api-key-visible-catalog-item = activation_permission_key
visible_family = activation_permission_key
visible_masked_value = iapk_****************
runtime = false
production = false
external_http = false
secret_visible = false
```

This makes the permission-key family visible to supervisors directly among Admin API Keys while keeping it non-runtime and non-production.
The Admin API Keys panel must also expose this key family as a visible key type:

```text
data-admin-api-keys-type-activation-permission = true
data-admin-api-key-type = activation_permission_key
runtime_api_key = false
production_key = false
external_http = false
stored_secret_visible = false
```

## Guardrails

```json
{
  "runtime_enabled": false,
  "production_allowed": false,
  "external_http_enabled": false,
  "raw_secret_visible": false
}
```

## Audit events

```text
integration_task_created
integration_task_suspended
integration_task_resumed
integration_task_revoked
integration_task_cancelled
integration_activation_permission_key_issued
```

## Production rule

Activation Permission Key does not grant production, runtime connector approval, external HTTP, or access to customer credentials.
Production access remains blocked behind a separate production gate, security review, customer endpoint binding approval, and operator sign-off.

## 13B-R4-UX visible catalog item quality

The visible Admin API Keys catalog item must be compact, responsive, and overflow-safe.

```text
ui_marker = pmk-iapk-card
masked_key_wrap = true
layout = responsive_grid
overflow_safe = true
guardrails_visible = true
```

## 13B-R5 visible generation action

The visible Admin API Keys catalog item includes a direct generation action:

```text
data-admin-api-key-visible-generate-button = true
data-admin-api-key-visible-generated-once = true
action = Generate Activation Permission Key
raw_key_visible_once = true
stored_list_value = masked_only
runtime = false
production = false
external_http = false
secret_visible = false
```

If no eligible pilot task exists, the UI may create a sandbox-only pilot task before extracting the activation permission key.

## 13B-R5A visible raw key output repair

The visible Admin API Keys generation action must preserve the one-time raw output after the card is re-rendered.

```text
fresh_output_selector = data-admin-api-key-visible-generated-once
raw_output_source = activation_permission_key_once
visible_once_dataset = true
masked_list_after_refresh = true
```

## 13B-R5B visible generation capture fix

The visible Admin API Keys generation button uses a capture-phase handler to preserve the one-time raw output after UI re-render.

```text
handler = visibleGenerateActivationPermissionKeyCaptureFix13B
output_selector = data-admin-api-key-visible-generated-once
dataset.visibleOnce = true
raw_output_source = activation_permission_key_once
masked_value_after_refresh = true
runtime = false
production = false
external_http = false
secret_visible = false
```

## 13B-R5C always-new-task generation

The visible Admin API Keys generation button creates a fresh sandbox-only pilot task before issuing the activation permission key.

```text
generation_strategy = visible_generate_always_new_task_13b
task_status = pending_supervisor_review
raw_key_visible_once = true
stored_list_value = masked_only
runtime = false
production = false
external_http = false
secret_visible = false
```

This avoids selecting older suspended, revoked, cancelled, or otherwise ineligible pilot tasks.

## 13B-R6 pilot activation control UX

The Pilot Controls activation permission output area must be compact, responsive, and overflow-safe.

```text
ui_marker = data-admin-pilot-activation-control
output_wrap = data-admin-pilot-activation-output-wrap
guardrails_marker = data-admin-pilot-activation-control-guardrails
raw_key_wrap = true
overflow_safe = true
```


## 13B isolated Admin UI recovery

The 13B Admin UI is isolated from `admin_api_keys.js`.

- UI script: `processual_api/static/js/admin_integration_pilot_controls_13b.js`
- License panel: `data-admin-integration-activation-license-panel`
- Tracking panel: `data-admin-integration-pilot-tracking-panel`
- API Keys original file remains untouched by 13B panels.

Guardrails remain false: runtime, production, external HTTP, and stored raw secret visibility.
