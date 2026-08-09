# Enterprise Sandbox Qualification 18

## Purpose

The Enterprise Settings surface can now prepare a customer-specific sandbox qualification without creating a runtime connector or handling credential values.

The workflow is intentionally **identifier-only**. It selects server-defined credential profiles, integration scopes, and declarations that required customer inputs are available. It does not accept the underlying API keys, OAuth secrets, passwords, access tokens, private keys, certificate private keys, webhook secrets, connection strings, or customer endpoint secrets.

## Server-authoritative catalog

`GET /settings/enterprise-integration` exposes `qualification_catalog` only for an eligible Enterprise Integration entitlement.

The catalog is derived from the central credential-profile and integration-scope registries. The browser does not invent profile IDs, scope IDs, access levels, risk levels, required inputs, or security-control requirements.

For locked plans the catalog remains empty.

## Evaluation contract

`POST /settings/enterprise-integration/sandbox-qualification` accepts:

- `credential_profile_id`
- `requested_scope_ids`
- `provided_input_ids`

The endpoint validates all identifiers against the central catalogs and evaluates readiness server-side.

The result always retains these invariants:

- `environment = sandbox`
- `persisted = false`
- `production_allowed = false`
- `runtime_connector_approved = false`
- customer-submitted security-control approvals are not accepted

Customer input completion can only move the qualification to the supervised security-review boundary. It cannot authorize runtime or production use.

## UI behavior

The Settings qualification workspace is progressive enhancement over the existing Enterprise console.

It contains only:

- a server-populated credential-profile selector
- server-populated scope checkboxes
- server-populated input-presence checkboxes
- an evaluate action that calls the sandbox qualification endpoint

There are intentionally no text/password fields for credential material and no controls for security approval, runtime activation, or production activation.

Errors fail closed. The UI may report that evaluation is unavailable, but it never infers an approval from client state.

## Next boundary

The next productization step may persist a safe qualification draft containing catalog identifiers and customer-input presence only. Any persistence design must continue to reject raw secret material and must keep supervised security decisions in a separate privileged workflow.

Production connector activation remains out of scope until an explicitly approved runtime-connector phase.
