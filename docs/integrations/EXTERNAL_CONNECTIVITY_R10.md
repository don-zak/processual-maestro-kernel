# EXTERNAL-CONNECTIVITY-R10 - Qualification and Sandbox Keys

## Status

Implemented and verified as phase 2 of the compressed four-phase external-connectivity plan.

phase_1_readiness_completed=true
phase_2_qualification_completed=true
phase_3_real_sandbox_started=false
real_sandbox_connection_attempted=false
production_connectivity_enabled=false

## Purpose

R10 implements governed, one-time qualification keys and sandbox API keys on top of the canonical R8/R9 external-connectivity case store.

A current R9 supervisor readiness attestation is required before qualification-key issuance. Qualification redemption is client-bound, revision-bound, time-bounded, and one-time. Sandbox-key issuance is permitted only after successful qualification redemption and only for scopes declared by the selected connector contract.

R10 performs no external HTTP, DNS, socket, provider-SDK, credential-resolution, runtime connector, sandbox transport, or production operation.

## Implemented scope

- docs/integrations/EXTERNAL_CONNECTIVITY_R10.md
- processual_api/integrations/external_connectivity_cases.py
- processual_api/integrations/__init__.py
- processual_api/services/external_connectivity_case_store.py
- processual_api/services/external_connectivity_qualification.py
- processual_api/schemas/external_connectivity.py
- processual_api/schemas/__init__.py
- processual_api/main.py
- tests/test_external_connectivity_key_contracts_r10.py
- tests/test_external_connectivity_qualification_service_r10.py
- tests/test_external_connectivity_key_lifecycle_r10.py
- tests/test_external_connectivity_key_routes_r10.py
- tests/test_external_connectivity_r10_document_and_exports.py

## Public contracts

The integration package publicly exports:

- ExternalConnectivityQualificationKey
- ExternalConnectivityQualificationKeyStatus
- ExternalConnectivitySandboxApiKey
- ExternalConnectivitySandboxApiKeyStatus

The contracts store SHA-256 hashes only. Raw qualification and sandbox keys are returned once at issuance and are never persisted.

## API routes

- POST /settings/admin/external-connectivity/cases/{case_id}/qualification-key
- POST /settings/admin/external-connectivity/cases/{case_id}/qualification-key/{qualification_key_id}/revoke
- POST /settings/client/external-connectivity/qualification/redeem
- POST /settings/admin/external-connectivity/cases/{case_id}/sandbox-api-key
- POST /settings/admin/external-connectivity/cases/{case_id}/sandbox-api-key/{sandbox_api_key_id}/suspend
- POST /settings/admin/external-connectivity/cases/{case_id}/sandbox-api-key/{sandbox_api_key_id}/revoke

All five administrative mutations require a centrally validated supervisor session. Identifiers are generated server-side. Case identifiers in mutation paths are bound to the stored key case.

## Qualification lifecycle

qualification_key_one_time=true
qualification_key_client_bound=true
qualification_key_attestation_bound=true
qualification_key_revision_bound=true
qualification_key_time_bounded=true
raw_qualification_key_persisted=false
constant_time_key_comparison=true

The qualification key can be redeemed only once by the exact client recorded on the approved external-connectivity case. Wrong clients, stale revisions, expired keys, expired attestations, revoked keys, and repeat redemption are rejected without store mutation.

## Sandbox-key lifecycle

sandbox_api_key_one_time=true
sandbox_key_connector_bound=true
sandbox_key_scope_bound=true
sandbox_key_case_bound=true
sandbox_key_revision_bound=true
sandbox_key_time_bounded=true
raw_sandbox_key_persisted=false
unsupported_connector_scope_rejected=true
suspend_and_revoke_supported=true

Sandbox scopes must be a non-empty unique subset of capability scopes declared by the case connector contract. Foreign connector scopes are rejected without modifying the canonical store.

## Security and integrity invariants

supervisor_write_guard_enabled=true
canonical_case_store_used=true
parallel_key_store_created=false
server_generated_identifiers=true
optimistic_revision_checks=true
connector_scope_binding=true
route_case_binding=true
safe_case_response_projection=true
raw_secret_echoed=false
raw_session_key_persisted=false
raw_key_hash_returned=false

## Non-authority boundary

network_access_performed=false
external_http_enabled=false
socket_access_enabled=false
dns_resolution_performed=false
credentials_resolved=false
provider_sdk_invoked=false
sandbox_transport_invoked=false
runtime_connector_enabled=false
production_allowed=false
automatic_activation_allowed=false

Issuing a sandbox API key establishes governed local authorization metadata only. It does not activate a connector, resolve a secret, contact a customer system, execute a sandbox request, or grant production access.

## Regression coverage

r10_pre_document_tests=28_passed
r8_r9_compatibility_tests=117_passed
combined_pre_document_tests=145_passed

The R10 documentation and export suite adds six acceptance tests. Focused regression covers R8/R9/R10 contracts, canonical storage, supervisor-session guards, connector bindings, connector operation plans, readiness evaluation, provider-binding readiness, and outbound TLS readiness.

## Acceptance criteria

- R10 contracts are importable from processual_api.integrations.
- Qualification issuance requires a current R9 supervisor readiness attestation.
- Raw keys are visible exactly once and only their SHA-256 hashes are stored.
- Hash comparison uses constant-time comparison.
- Client, case, revision, expiry, and connector-scope bindings are enforced.
- Administrative routes require a validated supervisor session.
- Route responses expose safe API models and never expose key hashes.
- R8 and R9 external-connectivity behavior remains compatible.
- No network, DNS, socket, HTTP, provider SDK, credential resolution, sandbox transport, runtime, or production operation occurs.

## Phase 3 boundary

Phase 3 may introduce a strictly governed real sandbox connectivity attempt using an approved sandbox key, exact connector scope, customer-supplied references, explicit supervisor authorization, and complete audit evidence.

R10 itself performs no real sandbox connection, invokes no external transport, reads no credential, and grants no production authority.
