# INTEGRATION-ADAPTERS-11C — Adapter Contracts

Status: `draft_review`.
Runtime connector approved: `false`.
Real credentials approved: `false`.
External HTTP calls approved: `false`.
Customer-specific connector approved: `false`.

This phase adds declarative adapter contracts on top of the 11A sector profiles,
11A-R1 existing integration primitive audit, and 11B scope catalog. It does not
create real customer connectors, endpoints, credentials, HTTP clients, or production
write actions.

## 1. Purpose

11C defines the contract layer between Maestro tasks and future customer-specific
connectors.

An adapter contract defines:

- supported sectors;
- adapter domains;
- required read scopes;
- optional write scopes;
- restricted scopes;
- safe operations;
- prohibited operations;
- customer prerequisites;
- Enterprise review requirement;
- sandbox-before-production requirement;
- supervisor approval requirement for production writes.

## 2. Initial adapter contracts

The initial contract set includes:

- CRM Adapter Contract;
- Billing Adapter Contract;
- Ticketing Adapter Contract;
- Order Management Adapter Contract;
- Network Assurance Adapter Contract;
- Document Adapter Contract;
- Banking KYC Adapter Contract;
- Government Case Adapter Contract;
- Research Dataset Adapter Contract;
- University Student Adapter Contract;
- Generic Enterprise Helpdesk Adapter Contract.

## 3. Relationship to scope catalog

Every adapter contract must reference scopes from the 11B integration scope catalog.
A contract must not invent a scope outside the catalog.

Read scopes describe safe inspection and summarization capabilities. Optional write
scopes describe actions that may be drafted, created, routed, or updated under
supervisor-approved governance. Restricted scopes describe operations that are not
enabled by default and require later customer-specific scoping.

## 4. Non-runtime guardrails

11C must not add:

- real customer endpoints;
- real customer credentials;
- external HTTP calls;
- OAuth secrets;
- mTLS certificates;
- webhook secrets;
- customer-specific connector runtime;
- production write behavior;
- background synchronization;
- direct customer database access.

## 5. Contract posture

All contracts remain review-led. They are readiness objects, not live integrations.

Every contract requires:

- API documentation;
- sandbox access;
- test credential policy;
- scope matrix;
- technical contact;
- acceptance criteria;
- security requirements;
- Enterprise review;
- sandbox validation before production;
- supervisor approval for production write behavior.

## 6. Examples of safe and prohibited behavior

Safe behavior includes reading approved records, summarizing context, drafting notes,
preparing support responses, previewing order impact, and creating governed tickets.

Prohibited behavior includes account mutation, billing adjustment, transaction
execution, network writes, permit approval, grade updates, KYC finalization, credit
approval, contract signing, and publication of embargoed research results without
explicit future approval.

## 7. Relationship to existing integration primitives

11C must align with the existing primitives documented in 11A-R1:

- `external_partner`;
- `service_integration`;
- API Key for integration;
- `/settings/api-key-integration`;
- integration key provisioning, rotation, and deactivation;
- Enterprise integration plans;
- safe usage logging.

It must not create a second key lifecycle.

## 8. Publication restrictions

This contract layer must not be used as:

- production connector approval;
- customer API compatibility guarantee;
- credential approval;
- security approval;
- restricted action approval;
- acceptance-test approval;
- proof that a customer-specific connector exists.

A later phase must add credential profiles, readiness checks, acceptance criteria,
and customer-specific connector work before production integration.
