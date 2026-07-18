# External Connectivity 16E-R7

## Immutable reference-only sandbox evidence bundle

`EXTERNAL-CONNECTIVITY-16E-R7` adds deterministic local evidence projection for the governed R5 workflow result and R6 fault result.

R7 receives an already-created result object. It never invokes the workflow, fault simulator, transport, dispatcher, secret manager, network, runtime, route, persistence layer, exporter, or production connector.

## Evidence contract

The declared contract is:

```text
telecom_ticketing_local_sandbox_evidence_contract
```

It references the governed workflow:

```text
telecom_ticketing_deterministic_sandbox_read_workflow
```

The accepted source types are:

```text
ConnectorSandboxReadWorkflowResult
ConnectorSandboxReadFaultResult
```

## Public contracts

```text
ConnectorSandboxEvidenceContract
ConnectorSandboxEvidenceAssessment
ConnectorSandboxEvidenceRequest
ConnectorSandboxEvidenceBundle
```

The public projection helper is:

```text
build_connector_sandbox_evidence_bundle
```

## Source kinds

```text
sandbox_read_workflow_result
sandbox_read_fault_result
```

R5 successful results preserve the synthetic resource and five safe metadata references.

R6 fault results preserve the synthetic fault reference and fault profile reference without adding payload metadata.

## Bundle statuses

| Status | Meaning |
|---|---|
| `evidence_captured` | A validated safe R5 or R6 result was projected |
| `invalid_source_result` | Required source validation state was absent |
| `unsafe_source_rejected` | A forged source contained an enabled unsafe flag |
| `contract_blocked` | The R7 evidence contract was unavailable or unsafe |

A rejected source never contributes its result reference or metadata to the bundle.

## Required evidence properties

Every bundle remains:

```text
deterministic=True
immutable=True
reference_only=True
local_only=True
non_persistent=True
export_safe=True
```

## Default-deny contract flags

```text
source_execution_allowed=False
payload_body_allowed=False
raw_response_allowed=False
secret_material_allowed=False
credential_resolution_allowed=False
dispatcher_invocation_allowed=False
network_access_allowed=False
persistence_allowed=False
background_task_allowed=False
external_export_execution_allowed=False
route_exposure_allowed=False
runtime_enabled=False
production_allowed=False
```

## Default-deny bundle evidence

```text
source_executed=False
payload_body_included=False
raw_response_included=False
secret_material_included=False
credentials_resolved=False
dispatcher_invoked=False
network_accessed=False
bundle_persisted=False
background_task_created=False
external_export_executed=False
route_exposed=False
runtime_used=False
production_used=False
```

Any attempt to enable these bundle fields is rejected by the frozen contract.

## Unsafe flag projection

R7 records flag-name references such as:

```text
external_http_used_false_reference
network_attempted_false_reference
production_used_false_reference
```

A forged enabled flag is represented only by a safe marker such as `external_http_used_true_reference`, while the source result itself is rejected.

## Reference-only fields

The bundle may include safe references for evidence ID, source request, workflow, plan, fault profile, source status, reason code, synthetic result, result type, source, metadata, and validation state.

R7 does not include payload bodies, response bodies, HTTP headers, authorization values, passwords, tokens, raw secrets, private keys, certificates, endpoint URLs, personal data, or production identifiers.

## No source execution

The R7 module does not import or call:

```text
execute_connector_sandbox_read_workflow
execute_connector_sandbox_read_fault
ConnectorDeterministicSandboxReadWorkflow
ConnectorDeterministicSandboxReadFaultSimulator
ConnectorDeterministicFakeSandboxTransport
```

R7 only validates and projects a source result supplied by its caller.

## Determinism

Building an evidence bundle twice from the same immutable source result produces equal bundles.

R7 does not use random identifiers, a real clock, sleep, network state, database state, environment secrets, or background workers.

## Persistence and export

R7 does not persist a bundle and does not execute an external export.

`export_safe=True` means that the bundle contains safe reference-only material. It does not authorize an export operation.

## Testing requirements

R7 tests cover registry immutability, frozen contracts, all R6 fault statuses, R5 evidence, deterministic repetition, invalid state refusal, forged unsafe source rejection, unsafe bundle flag rejection, raw reference rejection, no execution-layer imports, reference-only fields, documentation markers, and package exports.

## Explicit non-goals

R7 does not add a database, evidence retention policy, download route, API route, background exporter, operator endpoint, real secret, real network transport, runtime connector, or production activation.

## Gate after R7

R7 completes the deterministic local-only series. Any real operator sandbox work must begin under a separate 16F gate.

The next planned phase is:

```text
EXTERNAL-CONNECTIVITY-16F-R1
Operator sandbox endpoint reference intake
```

16F requires operator-provided endpoint, authentication method, secret-manager provider, allowlist, TLS requirements, tenant binding, read-only scope approval, security review, audit policy, and kill switch.
