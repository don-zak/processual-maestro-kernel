# Operator Pilot Handoff 14A

Status: `draft_review`

## Purpose

This phase adds a supervisor-facing operator pilot handoff page and a safe
handoff package contract. It prepares a sandbox-only integration discussion for
external organizations without approving production access, runtime connectors,
customer credentials, production writes, or external HTTP calls.

## Supervisor page

The Admin supervisor area includes:

- Operator pilot handoff status.
- Required organization input checklist.
- Supported organization types and domains.
- Safe replay tools:
  - Rebuild safe package.
  - Copy input checklist.
  - Copy Markdown.
  - Export Markdown.
- Pilot success criteria.
- Supervisor next actions.
- Sandbox guardrails.

## Supported organization types

The handoff package is no longer telecom-only. It supports:

- Telecom operators.
- Banks and fintech institutions.
- Government and public services.
- Universities and research organizations.
- Healthcare administration.
- Insurance providers.
- Utilities and energy providers.
- Logistics and transport operators.
- Enterprise helpdesk and service desks.
- Legal and compliance teams.

## Required organization inputs

Before any pilot can move forward, the external organization must provide:

- API documentation.
- Sandbox base URL.
- Authentication method.
- Allowed scopes matrix.
- Restricted scopes matrix.
- Rate limits and throttling policy.
- Test account or sandbox tenant.
- Sample request and response payloads.
- Error code catalog.
- Data retention and masking constraints.
- Security review contact.
- Incident escalation contact.
- Production approval path.

## Guardrails

This phase is explicitly safe:

- `sandbox_only=true`
- `production_allowed=false`
- `runtime_connector_approved=false`
- `customer_credentials_present=false`
- `external_http_allowed=false`
- `production_writes_allowed=false`
- `automatic_activation_allowed=false`

## Non-goals

This phase does not:

- Create a runtime connector.
- Call an external API.
- Store customer credentials.
- Approve production.
- Approve production writes.
- Change authentication or login.
- Change API key lifecycle behavior.

## Next phase

A later phase may add a protected JSON or Markdown export route if required.
That route must reuse the same guardrails and must remain supervisor-scoped.
