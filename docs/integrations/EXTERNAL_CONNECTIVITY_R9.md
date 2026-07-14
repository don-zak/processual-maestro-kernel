# EXTERNAL-CONNECTIVITY-R9 — Reference Intake and Supervisor Readiness

## Status

Implemented and verified as phase 1 of the compressed four-phase external-connectivity plan.

phase_1_readiness_completed=true
phase_2_qualification_implemented=false
real_sandbox_connection_attempted=false
production_connectivity_enabled=false

## Purpose

R9 provides the governed intake, reference validation, automated readiness review, and supervisor readiness-decision surface required before qualification or sandbox credentials may be issued.

The implementation accepts identifiers and references only. It does not resolve credentials, invoke provider SDKs, perform network access, issue qualification keys, or authorize runtime connectivity.

## Implemented scope

- processual_api/integrations/external_connectivity_cases.py
- processual_api/integrations/__init__.py
- processual_api/services/external_connectivity_case_store.py
- processual_api/services/external_connectivity_intake.py
- processual_api/schemas/external_connectivity.py
- processual_api/schemas/__init__.py
- processual_api/main.py
- tests/test_external_connectivity_supervisor_attestation_r9.py
- tests/test_external_connectivity_intake_service_r9.py
- tests/test_external_connectivity_routes_r9.py
- tests/test_external_connectivity_r9_document_and_exports.py

## Public contracts

The integration package publicly exports:

- SupervisorReadinessAttestation
- SupervisorReadinessDecision
- is_supervisor_readiness_attestation_current

Supervisor attestations are immutable, assessment-bound, reference-package-fingerprint-bound, time-bounded, and non-authoritative for runtime or production connectivity.

## API routes

- GET /settings/admin/external-connectivity/cases
- POST /settings/admin/external-connectivity/cases
- GET /settings/admin/external-connectivity/cases/{case_id}
- POST /settings/admin/external-connectivity/cases/{case_id}/reference-package
- POST /settings/admin/external-connectivity/cases/{case_id}/readiness-review
- POST /settings/admin/external-connectivity/cases/{case_id}/supervisor-decision

All mutating routes are protected through the central validated supervisor-session write guard.

## Security and integrity invariants

supervisor_write_guard_enabled=true
raw_customer_secret_accepted=false
raw_secret_echoed=false
server_generated_identifiers=true
optimistic_revision_checks=true
prior_approval_invalidated_on_resubmission=true
audit_events_redacted=true
authoritative_connector_bindings_used=true
parallel_case_store_created=false

The service validates connector target references, secret references, and credential-profile references against authoritative registries before readiness approval.

## Non-authority boundary

network_access_performed=false
external_http_enabled=false
socket_access_enabled=false
dns_resolution_performed=false
credentials_resolved=false
provider_sdk_invoked=false
provider_binding_created=false
qualification_key_issued=false
sandbox_api_key_issued=false
runtime_enabled=false
production_allowed=false

A readiness approval means that the submitted reference package satisfies the R9 intake contract. It does not authorize network access, secret resolution, sandbox execution, or production execution.

## Regression coverage

r9_direct_tests=39_passed
r8_compatibility_tests=78_passed
combined_pre_document_tests=117_passed

R9-4 adds six documentation and public-export contract tests. The focused regression also covers connector bindings, operation plans, readiness evaluation, operator sandbox intake, secret-provider readiness, outbound TLS readiness, and supervisor write-guard behavior.

## Acceptance criteria

- Public R9 contracts are importable from processual_api.integrations.
- The intake service uses the canonical external-connectivity case store.
- Raw credentials and secret values are rejected.
- Supervisor decisions require a validated supervisor write session.
- Stale revisions and mismatched fingerprints are rejected.
- Resubmission invalidates an earlier readiness approval.
- OpenAPI exposes the governed R9 request and response models.
- Existing R8 contracts remain compatible.
- No network, DNS, socket, HTTP, provider SDK, or credential-resolution operation occurs.

## Phase 2 boundary

Phase 2 begins only after R9 passes focused and full regression and is committed through the controlled publication checkpoint.

Phase 2 may implement qualification and governed sandbox-key issuance. R9 itself issues no qualification key, creates no sandbox API key, performs no real external connection, and grants no production authority.
