# EXTERNAL-CONNECTIVITY-16E-R4

## Deterministic local fake sandbox transport

`EXTERNAL-CONNECTIVITY-16E-R4` adds a deterministic local fake transport
for the governed telecom ticketing sandbox pilot.

The selected mode is:

`deterministic_local_reference_only_fake_transport`

Its response content mode is:

`synthetic_reference_metadata_only`

The implementation produces a deterministic synthetic read result without
executing a real connector operation.

## Selected reference graph

The fake transport contract connects:

- fake transport:
  `telecom_ticketing_deterministic_fake_sandbox_transport`
- disabled base transport:
  `telecom_ticketing_disabled_no_network_transport`
- sandbox pilot:
  `telecom_ticketing_read_only_sandbox_pilot`
- secret-manager contract:
  `telecom_operations_customer_vault_secret_manager_contract`
- operation plan:
  `telecom_ticketing_reference_sandbox_ticket_read_operation_plan`
- connector:
  `telecom_ticketing_reference`
- environment: `sandbox`
- access: `read-only`

The fake implementation remains local-only and sandbox-only.

## Declared contracts

The phase declares:

- `ConnectorFakeSandboxContract`
- `ConnectorFakeSandboxAssessment`
- `ConnectorFakeSandboxRequest`
- `ConnectorFakeSandboxResult`
- `ConnectorDeterministicFakeSandboxTransport`

The fake request wraps the existing reference-only
`ConnectorTransportRequest`.

It does not introduce an HTTP request model.

## Mandatory guardrails

The following statements are normative:

- local-only
- sandbox-only
- read-only
- deterministic synthetic read result
- synthetic reference metadata only
- no payload body
- no secret access
- no credential resolution
- no dispatcher invocation
- no network
- no HTTP
- no socket
- no persistence
- no route
- no worker
- no runtime
- no production

The phase does not:

- open a network connection;
- call an external endpoint;
- call an HTTP client;
- open a socket;
- invoke `ConnectorMockDispatcher`;
- invoke `ConnectorNoNetworkTransport`;
- execute the operation plan;
- read an API key;
- read a password;
- read a token;
- read private-key material;
- resolve a customer vault reference;
- accept a payload body;
- accept request headers;
- persist request or result data;
- generate random identifiers;
- read the current clock;
- create a background task;
- expose a FastAPI route;
- enable a runtime connector;
- authorize production.

## Deterministic synthetic response

For a valid reference-only request, the local fake transport returns:

- status: `synthetic_read_result`;
- reason code:
  `deterministic_synthetic_ticket_reference`;
- synthetic resource:
  `synthetic_ticket_reference`;
- synthetic resource type:
  `synthetic_ticket_resource_type_reference`;
- fixture source:
  `deterministic_local_fixture_v1_reference`.

The metadata references are fixed:

- `synthetic_ticket_state_open_reference`
- `synthetic_ticket_priority_normal_reference`
- `synthetic_ticket_channel_api_reference`
- `synthetic_ticket_owner_unassigned_reference`
- `synthetic_ticket_created_at_fixed_reference`

These are synthetic reference labels, not a real ticket body.

## Execution flags

Every successful or rejected result preserves:

- real transport attempted: false;
- dispatch attempted: false;
- operation executed: false;
- payload body used: false;
- secret accessed: false;
- credentials resolved: false;
- external HTTP used: false;
- socket used: false;
- payload persisted: false;
- background task created: false;
- runtime used: false;
- production used: false.

## Safe rejection behavior

The fake transport returns safe non-executing results for:

- unknown fake transport references;
- invalid base transport references;
- operation-plan mismatches;
- invalid contract reference graphs.

Rejected results contain no synthetic metadata.

## Relationship to previous phases

R4 consumes but does not modify:

- connector runtime contracts;
- connector registry;
- connector bindings;
- operation plans;
- mock dispatcher;
- sandbox pilot intake;
- secret-manager contracts;
- disabled no-network transport contracts.

The disabled R3 transport remains the default real transport boundary.

R4 is only a local deterministic test surface. Real sandbox HTTP and real
secret resolution remain outside this phase.
