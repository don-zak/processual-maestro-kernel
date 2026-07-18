# External Connectivity 16E-R6

## Deterministic fault, timeout, and safe-refusal contracts

`EXTERNAL-CONNECTIVITY-16E-R6` adds deterministic local fault simulation around the governed R5 sandbox-read workflow.

R6 does not enable a network connector, real timeout, retry worker, credential resolver, dispatcher, runtime route, persistence layer, or production execution.

## Scope

R6 provides:

- immutable sandbox-read fault profiles;
- nine deterministic synthetic fault kinds;
- immediate synthetic timeout results;
- safe-refusal results;
- immutable request, assessment, and result contracts;
- a read-only registry;
- validation and assessment helpers;
- a local deterministic fault simulator;
- explicit default-deny execution flags.

R6 preserves the R5 happy path without invoking or changing it.

## Governed workflow reference

All profiles reference:

```text
telecom_ticketing_deterministic_sandbox_read_workflow
```

The referenced workflow remains local-only, sandbox-only, read-only, deterministic, and synthetic-reference-only.

Its execution gates remain:

```text
external_http_allowed=False
runtime_enabled=False
production_allowed=False
```

## Declared fault profiles

| Fault kind | Result |
|---|---|
| `synthetic_timeout` | Immediate synthetic timeout |
| `synthetic_transport_unavailable` | Safe transport-unavailable refusal |
| `synthetic_authorization_denied` | Safe authorization denial |
| `synthetic_secret_reference_unavailable` | Safe secret-reference refusal |
| `synthetic_plan_rejected` | Safe plan rejection |
| `synthetic_operator_approval_missing` | Safe missing-approval refusal |
| `synthetic_security_review_missing` | Safe missing-review refusal |
| `synthetic_malformed_reference` | Safe malformed-reference refusal |
| `safe_refusal` | Generic deterministic refusal |

## Contracts

R6 declares frozen and slotted contracts:

```text
ConnectorSandboxReadFaultProfile
ConnectorSandboxReadFaultAssessment
ConnectorSandboxReadFaultRequest
ConnectorSandboxReadFaultResult
```

The local simulator is `ConnectorDeterministicSandboxReadFaultSimulator`.

The public helper is `execute_connector_sandbox_read_fault`.

## Deterministic timeout rule

`synthetic_timeout` returns immediately. It does not use sleep, a real clock, a network delay, an asynchronous timeout, or a background worker.

Repeated execution of the same request returns an equal result without waiting.

The timeout profile is:

```text
telecom_ticketing_synthetic_timeout_fault_profile
```

## Safe refusal

Every declared fault outcome is a safe refusal with:

```text
fault_injected=True
deterministic=True
immediate_result=True
safe_refusal=True
```

A synthetic failure does not mean that a real external operation failed. It is a local projection of a declared fault.

## Default-deny profile flags

```text
real_timeout_wait_allowed=False
retry_execution_allowed=False
automatic_retry_allowed=False
background_retry_allowed=False
network_attempt_allowed=False
secret_resolution_allowed=False
dispatcher_invocation_allowed=False
workflow_execution_allowed=False
payload_body_allowed=False
persistence_allowed=False
route_exposure_allowed=False
runtime_enabled=False
production_allowed=False
```

Any attempt to enable one of these flags is rejected.

## Default-deny result flags

```text
real_timeout_waited=False
retry_executed=False
automatic_retry_executed=False
background_retry_created=False
network_attempted=False
secret_resolved=False
dispatcher_invoked=False
workflow_executed=False
payload_body_used=False
payload_persisted=False
route_exposed=False
runtime_used=False
production_used=False
```

## Request validation

A request contains only `request_id`, `fault_profile_id`, and a reference-only R5 workflow request.

R6 validates the workflow, fake transport, disabled base transport, operation plan, simulation mode, and safe reference metadata.

The lower R3 contract rejects `simulation_mode=False` before R6 can execute.

Unknown profiles return `unknown_fault_profile` with `fault_injected=False` and `safe_refusal=True`.

Unsafe contract state returns `contract_blocked` without workflow execution.

## No R5 execution

R6 may assess the R5 contract, but it does not call:

```text
execute_connector_sandbox_read_workflow
ConnectorDeterministicSandboxReadWorkflow.run
ConnectorDeterministicFakeSandboxTransport.simulate
```

## No raw material

R6 does not accept or return payload bodies, response bodies, HTTP headers, passwords, tokens, raw secrets, private keys, certificates, or endpoint URLs.

## Registry

The immutable registry is `CONNECTOR_SANDBOX_READ_FAULT_PROFILES`.

The ordered identifiers are `SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES`.

Registry validation enforces unique identifiers, unique kinds, complete kind coverage, correct status mapping, the governed R5 reference, and default-deny flags.

## Testing requirements

R6 tests cover all nine profiles, deterministic results, immediate timeout behavior, invalid references, unsafe flag rejection, no R5 execution, no fake transport execution, no network or retry primitives, package exports, documentation markers, and R5 compatibility.

## Explicit non-goals

R6 does not add real HTTP, sockets, timeout waits, retries, workers, credentials, secret access, dispatcher execution, workflow execution, persistence, routes, runtime connectors, or production activation.

## Next phase

```text
EXTERNAL-CONNECTIVITY-16E-R7
Sandbox evidence bundle
```

R7 must remain immutable, deterministic, local-only, non-persistent by default, and free from payloads and secrets.
