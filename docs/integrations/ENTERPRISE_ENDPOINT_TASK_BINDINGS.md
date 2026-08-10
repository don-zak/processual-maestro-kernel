# Enterprise API Endpoint Binding & Task Injection

Status: `sandbox_configuration`

Production connector approved: `false`.
Runtime network connector approved: `false`.
Raw customer secret storage in endpoint bindings: `false`.

## Purpose

This contract completes the configuration layer between the existing Enterprise
Integration readiness controls and Maestro's declared sector adapter operations.
Customer APIs remain provider-specific at the edge, while Maestro workflows
consume canonical task inputs defined by a central task capability catalog.

The architecture is:

```text
Settings / Enterprise Integration
        -> Endpoint Binding
        -> Credential Profile Reference
        -> Request Parameter Binding
        -> Response Extraction / Field Mapping
        -> Canonical Maestro Task Input
        -> Governed Task / Workflow
```

Endpoint settings never carry raw API keys, OAuth secrets, passwords, tokens,
private keys, cookies, or Authorization headers.

## Coverage authority

`processual_api.integrations.adapter_contracts` remains the authority for what
integration domains and safe operations Maestro advertises. The task catalog in
`processual_api.integrations.integration_task_catalog` must cover every declared
`safe_operation` and every required adapter scope.

Current domain coverage:

- CRM;
- customer billing systems (separate from Maestro commercial billing);
- ticketing/helpdesk;
- order management;
- network assurance;
- document systems;
- banking/KYC/compliance;
- government/public administration cases;
- research datasets/experiments;
- university/student services;
- generic enterprise helpdesk/project/knowledge systems.

A contract test fails when a new safe adapter operation is added without a
canonical Maestro task capability.

## Canonical task contract

Each task declares:

- stable `task_id`;
- adapter contract;
- exact safe operation;
- operation class (`read`, `draft`, or `approval_gated_write`);
- required integration scopes;
- required and optional canonical input fields;
- output slot;
- sandbox posture;
- production approval posture.

Production auto-execution is false for every task in this stage.

## Endpoint binding contract

A binding supplies identifiers and non-secret connection metadata:

- binding/display identity;
- adapter contract and task IDs;
- credential profile reference;
- sandbox HTTPS base URL;
- HTTP method and endpoint path;
- required scopes;
- task-derived path/query parameter sources;
- non-sensitive static headers;
- response data path;
- canonical field mapping;
- success status codes and timeout.

Validation rejects:

- non-HTTPS base URLs;
- localhost/local/metadata destinations;
- embedded credentials;
- authentication headers or secret-like header values;
- tasks outside the selected adapter contract;
- credential profiles that do not support the adapter contract;
- scopes outside the adapter contract or missing task-required scopes;
- missing canonical required fields;
- fields outside the canonical task schema;
- production environment claims.

## Settings API

Enterprise-entitled clients receive:

```text
GET    /settings/enterprise-integration/task-catalog
GET    /settings/enterprise-integration/endpoint-bindings
PUT    /settings/enterprise-integration/endpoint-bindings/{binding_id}
DELETE /settings/enterprise-integration/endpoint-bindings/{binding_id}
POST   /settings/enterprise-integration/endpoint-bindings/{binding_id}/request-preview
POST   /settings/enterprise-integration/endpoint-bindings/{binding_id}/mapping-preview
```

Request preview builds the governed sandbox request shape without credential
material and explicitly reports `network_request_executed=false`.

Mapping preview accepts a sandbox/sample JSON response and produces the exact
canonical input object that would be injected into the selected Maestro task.

## Settings UI

The Enterprise Integration Settings surface dynamically loads the server task
catalog and endpoint binding inventory. It supports:

1. integration domain selection;
2. declared Maestro task selection;
3. compatible credential reference profile selection;
4. sandbox base URL and path configuration;
5. task-schema-derived field mapping;
6. sample response mapping preview;
7. schema-validated persistence;
8. persistent sandbox/production boundary messaging.

The UI does not contain credential value fields.

## Execution boundary

This stage intentionally does not bypass the existing Enterprise qualification
model. The endpoint binding and request preview prove that Maestro knows what to
call, what data to extract, and which canonical task receives it. Actual external
HTTP execution must remain behind the existing supervised sandbox security
qualification and a credential resolver that returns secrets only at execution
time.

This separation is mandatory: adding endpoint metadata must never implicitly
approve a runtime connector or production access.

## Tests

The bundle includes tests for:

- exact safe-operation coverage across all current adapter contracts;
- required scope coverage;
- prohibited-operation exclusion;
- approval-gated scope posture;
- all eleven current integration domains;
- endpoint/task/profile/scope compatibility;
- HTTPS/local/metadata/secret rejection;
- banking and billing canonical response mapping;
- request preview without credentials or network execution;
- Settings route registration and entitlement boundaries;
- safe persistence/list/delete behavior;
- mapping preview injection into canonical task inputs;
- UI server-authoritative catalog usage, accessibility, responsive behavior,
  sandbox language, and secret-field exclusion.
