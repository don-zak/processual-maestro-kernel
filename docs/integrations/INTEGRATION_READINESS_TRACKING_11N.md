# Integration Readiness Tracking 11N

Status: internal implementation foundation
Phase: INTEGRATION-READINESS-11N

## Purpose

The previous readiness surfaces show declarative readiness checks: what inputs and security controls are required before sandbox review. They do not yet prove that a specific client has submitted documents, that a supervisor has reviewed them, or that an item has moved from missing to provided or verified.

This phase adds a service-level tracking foundation for client-specific readiness cases. It is intentionally not a runtime connector and it does not add external HTTP, customer endpoints, credential storage, or production approval.

## Logical records

The foundation models the following logical records:

- readiness_case
- readiness_input_status
- readiness_security_control_status
- readiness_timeline_event
- safe_evidence_reference

These are service-level records in this phase. They can later be mapped to database tables or persisted storage after the schema is reviewed.

## Case fields

A readiness case carries:

- case_id
- client_id
- request_id
- adapter_contract_id
- credential_profile_id
- operational_profile_id
- status
- input_statuses
- security_control_statuses
- timeline
- assigned_supervisor
- sandbox_ready
- production_allowed=false
- runtime_connector_approved=false
- external_http_enabled=false
- raw_secret_visible=false

## Item statuses

Inputs and security controls can be:

- missing
- provided
- verified
- rejected

Verification requires an actor. A verified case can become sandbox_ready only when all required inputs and all required security controls are verified.

## Safe evidence references

The model accepts safe evidence references only, such as:

- document_ref
- ticket_ref
- vault_ref
- manual_note
- customer_portal_ref

The reference label must not contain secrets, tokens, passwords, bearer values, hardcoded endpoints, or raw credential material.

## Guardrails

This phase preserves:

- no raw secrets
- no customer credentials
- no customer endpoints
- no external HTTP
- no runtime connector
- no production connector approval
- no automatic sandbox approval unless required items are verified

## Relationship to readiness surfaces

The admin readiness surface can continue to show the declarative checks. A later UI phase can join those checks with readiness tracking cases to show what has been submitted, verified, rejected, or still missing for a specific client request.

## Out of scope

This phase does not add:

- database migration
- admin route
- client route
- UI table
- upload endpoint
- external connector
- production approval flow
- runtime execution

Those should be introduced only after this foundation is validated.
