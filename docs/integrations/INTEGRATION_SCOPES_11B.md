# INTEGRATION-SCOPES-11B — Integration Scope Catalog

Status: `draft_review`.
Production connector approved: `false`.
Real credentials approved: `false`.
External HTTP calls approved: `false`.
Customer-specific integration approved: `false`.

This phase adds a central integration scope catalog derived from the sector adapter
umbrella. It does not create customer endpoints, credentials, HTTP clients, runtime
connectors, or production write actions.

## 1. Purpose

11B turns the scopes declared in sector profiles into a central review-safe catalog.
The catalog defines the posture of each integration action before customer-specific
implementation begins.

Each cataloged scope records:

- scope identifier;
- domain;
- action;
- access level;
- risk level;
- supported sectors;
- supported key profiles;
- read-only pilot allowance;
- Enterprise review requirement;
- supervisor approval requirement;
- sandbox-before-production requirement;
- production approval boundary.

## 2. Access levels

The catalog uses three access levels:

| Access level | Meaning | Default risk | Default posture |
| --- | --- | --- | --- |
| read | Read-only inspection or summarization | low | Allowed in read-only pilots. |
| write | Drafting, creating, routing, or updating under control | high | Requires supervisor approval. |
| restricted | Sensitive finalization, adjustment, execution, or mutation | critical | Not enabled by default. |

## 3. Existing key profile alignment

11B must align with existing integration primitives documented in 11A-R1.

Read scopes can align with:

- `external_partner`;
- `service_integration`.

Write scopes can align with:

- `service_integration`.

Restricted scopes have no default key profile and require later scoping, approval,
and customer-specific governance.

## 4. Sector relationship

The catalog is derived from the 11A sector profiles:

- Telecom;
- Banking;
- Government;
- Research Center;
- University;
- Generic Enterprise.

If the same scope appears in more than one sector, the catalog keeps one central
scope record and records all sectors that use it. For example, `crm:read` can support
both Telecom and Generic Enterprise without creating duplicate scope definitions.

## 5. Pilot and production posture

Read-only pilots may use read scopes only.

Write scopes require supervisor approval and sandbox validation before production.

Restricted scopes represent high-risk operations such as billing adjustment, network
write, transaction execution, credit approval, permit approval, grade update, or
contract signing. They are not production enabled by this phase.

## 6. Non-implementation guardrails

11B must not add:

- real customer endpoints;
- real customer credentials;
- external HTTP calls;
- OAuth secrets;
- mTLS certificates;
- webhook secrets;
- customer-specific connector runtime;
- production write behavior;
- new key lifecycle separate from existing `service_integration` and
  `external_partner` primitives.

## 7. Relationship to 11A-R1

11A-R1 confirmed that Maestro already has access and readiness primitives, including
API Key for integration, service integration server-to-server access,
`/settings/api-key-integration`, integration key provisioning, rotation,
deactivation, Enterprise integration plans, and usage logging.

11B builds on those primitives by cataloging scopes. It does not replace the
existing key lifecycle or client readiness UI.

## 8. Publication restrictions

This catalog must not be used as:

- production connector approval;
- customer API compatibility guarantee;
- credential approval;
- restricted action approval;
- security approval;
- acceptance-test approval;
- proof that a customer-sector adapter exists.

A later phase must add adapter contracts, credential profiles, readiness checks, and
customer-specific connector work before production integration.
