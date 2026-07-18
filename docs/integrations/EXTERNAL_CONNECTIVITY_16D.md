# EXTERNAL-CONNECTIVITY-16D

## Disabled local mock dispatcher contracts

`EXTERNAL-CONNECTIVITY-16D` introduces immutable reference-only contracts
for validating connector dispatch requests locally.

The phase is:

- mock-only
- local-only
- reference-only
- default-deny

It is not a connector implementation and does not establish connectivity
with an operator, customer, institution, sandbox, or production system.

## Added contracts

The phase adds:

- `ConnectorDispatchStatus`
- `ConnectorDispatchRequest`
- `ConnectorDispatchResult`
- `ConnectorMockDispatcher`

The dispatcher performs only these local operations:

1. validates required reference metadata;
2. resolves an existing `16C` operation-plan reference;
3. verifies that the plan ends in `block_dispatch`;
4. verifies that execution guardrails remain disabled;
5. returns an immutable blocked result.

## Mandatory safety properties

The following statements are normative:

- mock-only
- local-only
- no network
- no customer endpoint
- no credentials
- no raw payload
- no persistence
- no route
- no worker
- no production
- no sandbox connectivity proof
- all dispatch results remain blocked

The dispatcher does not:

- issue an HTTP request;
- open a socket;
- resolve a secret;
- load a credential;
- write a file or database record;
- persist a request or result;
- emit a real audit event;
- create a task, thread, process, queue, or worker;
- expose an application route;
- activate a runtime connector;
- access sandbox or production infrastructure.

## Request contract

`ConnectorDispatchRequest` contains references and hashes only:

- `request_id`
- `plan_id`
- `operation_id`
- `tenant_reference`
- `payload_hash`
- `idempotency_key`
- `requested_at_reference`
- `expires_at_reference`
- `requester_reference`
- `approval_reference`
- `simulation_mode`

It contains no payload body, URL, endpoint, headers, password, token,
credential, private key, secret value, or customer data.

`simulation_mode` must always remain enabled.

## Result contract

Every `ConnectorDispatchResult` preserves:

- `dispatch_attempted = false`
- `operation_executed = false`
- `external_http_used = false`
- `credentials_resolved = false`
- `payload_persisted = false`
- `audit_event_emitted = false`
- `background_task_created = false`
- `production_used = false`

Attempting to construct a result with any execution flag enabled is
rejected.

A complete and valid local request receives:

- `dispatch_status = blocked`
- `reason_code = dispatch_disabled_by_contract`

Successful metadata validation does not grant execution authority.

## Safe outcomes

Only the following outcome statuses exist:

- `blocked`
- `invalid_request`
- `unknown_plan`
- `metadata_incomplete`
- `approval_reference_missing`
- `expired_reference`

No status represents execution, delivery, connectivity, runtime enablement,
sandbox success, or production readiness.

## Relationship to 16A, 16B, and 16C

This phase consumes existing `16C` plans without modifying them.

It does not change:

- runtime connector contracts;
- the connector registry;
- target references;
- secret references;
- environment bindings;
- credential profiles;
- adapter contracts;
- scope definitions;
- operation plans;
- approval requirements;
- audit projections.

Every accepted operation plan must remain `planning_only`, terminate with
`block_dispatch`, and keep execution, external HTTP, production, automatic
activation, and credential resolution disabled.

## Non-goals

`16D` is not:

- a transport implementation;
- an API client;
- a fake HTTP client;
- a sandbox connector;
- a customer connector;
- a credential adapter;
- an audit persistence service;
- a production approval.

Actual sandbox connectivity remains a separate reviewed phase requiring a
named connector, approved endpoint, documented API version, authentication
method, secret-manager reference, test tenant, data classification, rate
limits, acceptance criteria, and operator or customer authorization.
