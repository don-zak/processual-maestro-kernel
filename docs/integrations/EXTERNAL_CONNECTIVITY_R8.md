# EXTERNAL-CONNECTIVITY-R8

## Status

R8 contract, persistence, and OpenAPI-model scope is implemented and locally verified.
This phase is contract-only and remains default-deny.

route_implementation_included=False
runtime_enabled=False
production_allowed=False

## Purpose

R8 establishes the canonical External Connectivity Case specification without opening an external connection.
It defines immutable case and customer-reference contracts, readiness assessment boundaries, deterministic fingerprints, allowlisted state transitions, a redacted audit taxonomy, isolated persistence, and frozen OpenAPI models.

ExternalConnectivityCase references the existing IntegrationReadinessCase authority; it does not replace it or create a parallel readiness authority.

## Implementation scope

Production and export files:

- processual_api/integrations/external_connectivity_cases.py
- processual_api/services/external_connectivity_case_store.py
- processual_api/schemas/external_connectivity.py
- processual_api/integrations/__init__.py
- processual_api/schemas/__init__.py

Direct contract files:

- tests/test_external_connectivity_case_contracts_r8.py
- tests/test_external_connectivity_case_store_r8.py
- tests/test_external_connectivity_openapi_models_r8.py
- tests/test_external_connectivity_r8_document.py

No FastAPI route, provider adapter, connector dispatcher, credential resolver, DNS operation, socket operation, HTTP client, or production activation path is added by R8.

## Contract model

The canonical aggregate consists of:

- ExternalConnectivityCase: immutable lifecycle identity and default-deny authority flags.
- CustomerReferencePackage: reference-only customer material bound to a server case ID.
- ExternalConnectivityReadinessAssessment: immutable assessment bound to the exact package fingerprint.
- ExternalConnectivityCaseState: closed state catalog.
- ExternalConnectivityAuditEventType: closed and redaction-safe event taxonomy.

Customer package fingerprints use deterministic canonical JSON and SHA-256. Changing reference content changes the fingerprint and prevents an assessment from being silently reused for different material.

## State catalog

- draft
- customer_package_submitted
- under_automated_review
- needs_remediation
- ready_for_supervisor_approval
- readiness_approved
- qualification_key_issued
- qualification_redeemed
- sandbox_api_key_issued
- sandbox_authorized
- sandbox_suspended
- sandbox_revoked
- closed

state_transitions_allowlisted=True

## Allowlisted transitions

| Current state | Allowed target |
|---|---|
| draft | customer_package_submitted |
| draft | closed |
| customer_package_submitted | under_automated_review |
| under_automated_review | needs_remediation |
| under_automated_review | ready_for_supervisor_approval |
| needs_remediation | customer_package_submitted |
| ready_for_supervisor_approval | readiness_approved |
| ready_for_supervisor_approval | needs_remediation |
| readiness_approved | qualification_key_issued |
| qualification_key_issued | qualification_redeemed |
| qualification_redeemed | sandbox_api_key_issued |
| sandbox_api_key_issued | sandbox_authorized |
| sandbox_authorized | sandbox_suspended |
| sandbox_authorized | sandbox_revoked |
| sandbox_suspended | sandbox_authorized |
| sandbox_suspended | sandbox_revoked |
| sandbox_revoked | closed |

All other transitions are rejected. Case advancement returns a new revision and does not mutate the source aggregate.

## Audit taxonomy

- case_created
- customer_package_submitted
- automated_review_started
- remediation_required
- ready_for_supervisor_approval
- readiness_approved
- qualification_key_issued
- qualification_redeemed
- sandbox_api_key_issued
- sandbox_authorized
- sandbox_suspended
- sandbox_revoked
- case_closed
- transition_rejected
- prohibited_field_rejected

Audit payloads contain identifiers, references, fingerprints, state changes, and safe reason codes only. They do not contain raw credentials or raw secret material.

audit_events_redacted=True

## Prohibited-fields policy

Customer submissions are reference-only. Recursive prohibited-field detection rejects raw credential-bearing names, including:

- password
- raw_secret
- api_key
- client_secret
- private_key

Reference identifiers such as api_key_reference and secret_reference remain references and are not treated as raw values.

raw_customer_secret_accepted=False
raw_secret_visible=False

## Store contract

The store serializes deterministic JSON and validates duplicate case, package, and assessment identifiers. It also rejects orphan packages, package-fingerprint mismatches, corrupted JSON, and unknown schema versions.

Store path precedence is:

1. Explicit function path.
2. PMK_EXTERNAL_CONNECTIVITY_CASES_PATH.
3. data/external_connectivity_cases.json.

Writes use a temporary sibling file followed by atomic replacement. Tests override the path under tmp_path and do not share production data.

stores_test_isolated=True
atomic_write_enabled=True

## OpenAPI models

R8 exposes frozen, extra-forbid Pydantic request and response models:

- ExternalConnectivityCaseCreateRequest
- CustomerReferencePackageSubmissionRequest
- ExternalConnectivityCaseResponse
- ExternalConnectivityReadinessAssessmentResponse

The create model permits the sandbox environment only. Response authority flags remain false, and generated submission schemas expose no prohibited raw-secret properties.

openapi_models_exposed=True
raw_secret_properties_exposed=False

## Security invariants

raw_customer_secret_accepted=False
network_access_performed=False
external_http_enabled=False
socket_access_enabled=False
dns_resolution_performed=False
credentials_resolved=False
provider_binding_created=False
raw_secret_visible=False
runtime_enabled=False
production_allowed=False

The R8 modules do not import network clients, provider SDKs, secret-provider SDKs, or connector runtime dispatchers.

## Regression coverage

The direct contract, store, and OpenAPI suite passed before documentation:

direct_tests=71_passed

The focused suite covering integration contracts, readiness, tracking, sandbox intake, provider binding, outbound TLS, pilot activation validation, the R7 request-body contract, and FastAPI integration smoke passed:

focused_regression=368_passed

The documentation contract adds seven checks for identity, scope, states, audit taxonomy, security invariants, persistence/OpenAPI boundaries, and the R9 boundary.

## Acceptance criteria

raw_customer_secret_accepted=False
network_access_performed=False
state_transitions_allowlisted=True
audit_events_redacted=True
stores_test_isolated=True

## R9 boundary

R8 defines contracts and local persistence only. R9 owns customer reference submission workflows and readiness review behavior.

R9 may implement case creation or update, reference-package submission, completeness assessment, prohibited-field reporting, provider/reference consistency checks, TLS/network-policy reference validation, blockers, and remediation matrices.

R9 must still prohibit secret resolution, provider SDK initialization, DNS, sockets, HTTP, certificate loading, sandbox activation, and production activation.

r9_implementation_included=False
secret_resolution_included=False
external_connection_attempted=False
