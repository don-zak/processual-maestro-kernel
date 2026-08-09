# Enterprise Sandbox Qualification 18

## Purpose

The Enterprise Settings surface can prepare, save, and submit a customer-specific sandbox qualification without creating a runtime connector or handling credential values.

The workflow is intentionally **identifier-only**. It selects server-defined credential profiles, integration scopes, and declarations that required customer inputs are available. It does not accept the underlying API keys, OAuth secrets, passwords, access tokens, private keys, certificate private keys, webhook secrets, connection strings, or customer endpoint secrets.

## Server-authoritative catalog

`GET /settings/enterprise-integration` exposes `qualification_catalog` only for an eligible Enterprise Integration entitlement.

The catalog is derived from the central credential-profile, adapter-contract, and integration-scope registries. The browser does not invent profile IDs, scope IDs, access levels, risk levels, required inputs, or security-control requirements.

Each credential profile includes server-derived `allowed_scope_ids`. Those IDs are the union of scopes referenced by adapter contracts supported by that profile. The browser filters the selectable scopes with this list, and every server write independently enforces the same profile-to-scope compatibility. A scope that exists in the global catalog is still rejected when it is outside the selected profile's supported adapter contracts.

For locked plans the qualification catalog remains disabled and empty, and persisted qualification state is not exposed.

## Evaluation contract

`POST /settings/enterprise-integration/sandbox-qualification` accepts:

- `credential_profile_id`
- `requested_scope_ids`
- `provided_input_ids`

The endpoint validates all identifiers against the central catalogs, validates profile-to-scope compatibility, and evaluates readiness server-side. Evaluation remains non-persistent.

The result always retains these invariants:

- `environment = sandbox`
- `persisted = false`
- `production_allowed = false`
- `runtime_connector_approved = false`
- `security_controls_client_approvable = false` in the catalog
- customer-submitted security-control approvals are not accepted

Customer input completion can only move the qualification to the supervised security-review boundary. It cannot authorize runtime or production use.

## Safe draft persistence

`PUT /settings/enterprise-integration/sandbox-qualification/draft` persists a validated qualification draft for an eligible client. The stored object contains only:

- schema version
- lifecycle status and revision
- credential profile identifier
- requested scope identifiers
- provided-input presence identifiers
- creation/update timestamps

It does not persist readiness output, security approvals, credential values, endpoint values, runtime approval, or production approval.

Readback is rebuilt through the current server catalogs. If a stored profile, scope, or input identifier becomes invalid, the draft fails closed and is not exposed as a valid draft.

`POST /settings/enterprise-integration/sandbox-qualification/draft/submit` transitions a valid draft to `pending_review`. Submission does not approve any security control and leaves `sandbox_ready`, production, and runtime authority fail-closed.

`GET /settings/enterprise-integration` includes a safe `qualification_draft` projection for eligible clients so the UI can restore the server-authoritative draft.

## Supervised revision workflow

A supervisor can read a submitted qualification draft through:

`GET /settings/admin/enterprise-integration/qualification-drafts/{user_id}`

This requires `admin:integration:qualification:read` through the existing supervision RBAC model.

A supervisor can request a customer revision through:

`POST /settings/admin/enterprise-integration/qualification-drafts/{user_id}/request-revision`

The write requires both:

- `admin:integration:qualification:review` on the authenticated supervisor identity
- a validated supervisor session carrying the qualification-review scope

Revision reasons are fixed reason identifiers rather than free-form text. This prevents the qualification settings store from becoming an accidental channel for raw secrets or arbitrary support notes.

A revision request returns the submitted draft to `draft`, increments its revision, removes the prior submission timestamp, and exposes a client-safe review projection without the reviewer identity.

This phase intentionally does **not** add a qualification approval endpoint. Sandbox security approval requires a separate evidence-aware privileged decision contract. The existing `admin:integration:qualification:approve` RBAC scope is not sufficient by itself to infer evidence or activate a connector.

## UI behavior

The Settings qualification workspace is progressive enhancement over the existing Enterprise console.

It contains only:

- a server-populated credential-profile selector
- profile-compatible, server-populated scope checkboxes
- server-populated input-presence checkboxes
- an evaluate action
- a `Save draft` action
- a `Submit for supervised review` action

The workspace restores a persisted draft from the server. Submission first saves the current identifier selection, then submits that exact server-side draft, avoiding stale client submissions.

There are intentionally no text/password fields for credential material and no controls for security approval, runtime activation, or production activation.

Changing the credential profile clears prior scope and input selections and repopulates them from that profile's server-provided contract. Errors fail closed. The UI may report that evaluation, persistence, or submission is unavailable, but it never infers an approval from client state.

## Phase closure contract

This persistence/review phase is complete when the following remain true under regression testing:

- eligible clients receive only safe qualification metadata and their safe persisted draft
- locked clients receive no qualification catalog or persisted qualification state
- requested scopes must be compatible with the selected credential profile
- customer input presence is declarative and contains no underlying secret values
- stored drafts contain identifiers and lifecycle metadata only
- stale or corrupt stored identifiers fail closed on readback
- client submission cannot provide security-control approval
- supervisor reads require qualification-read authority
- supervisor revision writes require both review authority and a validated supervisor write session
- revision reasons are fixed identifiers, not free text
- no sandbox approval is inferred from review or submission
- runtime connector approval and production access remain false
- responsive, RTL-safe, keyboard-accessible UI behavior is preserved

Global CI failures outside these contracts do not change the qualification safety posture; they must be tracked and resolved in their owning workstreams.

## Next boundary

The next security-sensitive boundary is an evidence-aware sandbox approval decision for supervisors who hold `admin:integration:qualification:approve`. That design must define the evidence being approved, bind the decision to an immutable draft revision, record an audit event, and remain sandbox-only.

Production connector activation remains out of scope until an explicitly approved runtime-connector phase.
