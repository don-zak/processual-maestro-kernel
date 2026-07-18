# PILOT-HANDOFF-17C-R1 — Unified Handoff UI and Intake Preview

## Status

Implemented on a dedicated branch from `a988722948807c3150e6023c8a039d659a6390d6`.

## Purpose

17C-R1 replaces the cumulative Pilot Handoff presentation with a case-focused
workspace and adds a safe way to bring integration metadata into Maestro for
review and evaluation.

The central separation remains:

```text
Catalog != Case != Handoff Package != Runtime
```

## User experience

The workspace contains:

- a pilot identity header;
- a six-stage lifecycle rail;
- executive readiness counters;
- Overview, Intake & Validation, Required Inputs, Reviews & Controls,
  Pilot Plan, and Evidence & Audit tabs;
- one table for required inputs instead of repeated action cards;
- one table for controls and blockers;
- explicit loading, unauthorized, unavailable, and empty states;
- responsive layouts and reduced-motion support.

## How integration data enters Maestro

1. The organization or integration supervisor prepares a JSON manifest using
   schema `pilot-handoff-intake-17c-r1`.
2. The manifest contains references and technical metadata only: organization
   identifiers, adapter and credential-profile identifiers, API document and
   sandbox target references, requested scopes, sample references, DNS/TLS
   metadata, allowlist references, operations policies, governance policies,
   and evidence references.
3. The supervisor uploads the JSON file or pastes it into Intake & Validation.
4. The browser rejects oversize or obvious secret-bearing content.
5. Maestro sends it to the authenticated preview route:

   ```text
   POST /settings/admin/operator-pilot-handoff/intake-preview
   ```

6. The backend validates schema, sandbox-only scope, prohibited fields,
   completeness, and canonical digest.
7. The response exposes only assessment metadata, missing fields, warnings,
   review queue, next action, and digest. It never echoes the manifest.
8. A complete preview becomes ready for supervisor review; it does not grant
   sandbox qualification, runtime access, or production authority.

## Credential boundary

The intake manifest must never contain passwords, access tokens, API keys,
client secrets, authorization headers, private keys, or other secret values.
Credential values belong to a separately approved vault or secret-provider
binding after readiness review. Handoff carries only the credential profile
identifier and safe references.

## Security invariants

```text
preview_persisted=false
manifest_echoed=false
production_allowed=false
runtime_connector_approved=false
customer_credentials_present=false
external_http_allowed=false
automatic_activation_allowed=false
credentials_storage_allowed=false
```

The preview route requires `admin:integration_readiness:review` or wildcard
administrative authority through the existing authenticated dependency.

## Files

- `processual_api/main.py`
- `processual_api/services/operator_pilot_handoff_intake_preview.py`
- `processual_api/static/admin.html`
- `processual_api/static/js/admin_operator_pilot_handoff.js`
- `processual_api/static/js/admin_operator_pilot_handoff_17c.js`
- `processual_api/static/css/admin_operator_pilot_handoff_17c.css`
- `tests/test_operator_pilot_handoff_intake_preview_17c_r1.py`
- `tests/test_operator_pilot_handoff_intake_preview_route_17c_r1.py`
- `tests/test_operator_pilot_handoff_intake_preview_http_17c_r1.py`
- `tests/test_operator_pilot_handoff_dashboard_ui_17c_r1.py`

## Validation performed in the implementation workspace

- JavaScript syntax checks passed.
- Python compile checks passed.
- 33 static 14A/14D/14E/17C contract checks passed.
- Direct intake contract assertions passed.
- Full `pytest`, Ruff, Mypy, and browser proof remain merge gates in the
  complete `pmk314` project environment.

## Non-authority boundary

17C-R1 does not persist intake manifests, mutate case state, resolve secrets,
contact customer systems, execute connectors, issue qualification keys, start
a sandbox transport, or authorize production.
