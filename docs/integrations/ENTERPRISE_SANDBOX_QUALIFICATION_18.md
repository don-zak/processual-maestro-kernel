# Enterprise Sandbox Qualification 18

## Purpose

The Enterprise Settings surface can prepare a customer-specific sandbox qualification without creating a runtime connector or handling credential values.

The workflow is intentionally **identifier-only**. It selects server-defined credential profiles, integration scopes, and declarations that required customer inputs are available. It does not accept the underlying API keys, OAuth secrets, passwords, access tokens, private keys, certificate private keys, webhook secrets, connection strings, or customer endpoint secrets.

## Server-authoritative catalog

`GET /settings/enterprise-integration` exposes `qualification_catalog` only for an eligible Enterprise Integration entitlement.

The catalog is derived from the central credential-profile, adapter-contract, and integration-scope registries. The browser does not invent profile IDs, scope IDs, access levels, risk levels, required inputs, or security-control requirements.

Each credential profile includes server-derived `allowed_scope_ids`. Those IDs are the union of scopes referenced by adapter contracts supported by that profile. The browser filters the selectable scopes with this list, and the POST endpoint independently enforces the same profile-to-scope compatibility. A scope that exists in the global catalog is still rejected when it is outside the selected profile's supported adapter contracts.

For locked plans the qualification catalog remains disabled and empty.

## Evaluation contract

`POST /settings/enterprise-integration/sandbox-qualification` accepts:

- `credential_profile_id`
- `requested_scope_ids`
- `provided_input_ids`

The endpoint validates all identifiers against the central catalogs, validates profile-to-scope compatibility, and evaluates readiness server-side.

The result always retains these invariants:

- `environment = sandbox`
- `persisted = false`
- `production_allowed = false`
- `runtime_connector_approved = false`
- `security_controls_client_approvable = false` in the catalog
- customer-submitted security-control approvals are not accepted

Customer input completion can only move the qualification to the supervised security-review boundary. It cannot authorize runtime or production use.

## UI behavior

The Settings qualification workspace is progressive enhancement over the existing Enterprise console.

It contains only:

- a server-populated credential-profile selector
- profile-compatible, server-populated scope checkboxes
- server-populated input-presence checkboxes
- an evaluate action that calls the sandbox qualification endpoint

There are intentionally no text/password fields for credential material and no controls for security approval, runtime activation, or production activation.

Changing the credential profile clears prior scope and input selections and repopulates them from that profile's server-provided contract. Errors fail closed. The UI may report that evaluation is unavailable, but it never infers an approval from client state.

## Phase closure contract

This phase is complete when the following remain true under regression testing:

- eligible clients receive only safe qualification metadata
- locked clients receive no qualification profile or scope catalog
- requested scopes must be compatible with the selected credential profile
- customer input presence is declarative and contains no underlying secret values
- security-control approval cannot be submitted from the client workspace
- qualification evaluation is not persisted
- runtime connector approval and production access remain false
- responsive, RTL-safe, keyboard-accessible UI behavior is preserved

Global CI failures outside these contracts do not change the qualification safety posture; they must be tracked and resolved in their owning workstreams.

## Next boundary

The next productization step may persist a safe qualification draft containing catalog identifiers and customer-input presence only. Any persistence design must continue to reject raw secret material and must keep supervised security decisions in a separate privileged workflow.

Production connector activation remains out of scope until an explicitly approved runtime-connector phase.
