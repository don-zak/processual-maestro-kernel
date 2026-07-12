# External Connectivity 16F-R1

## Governed operator sandbox reference intake

`EXTERNAL-CONNECTIVITY-16F-R1` introduces a local reference-intake contract for the telecom ticketing operator sandbox.

The phase begins with all ten operator inputs absent and the declared status `pending_operator_input`.

R1 does not register an endpoint, create a binding, register a secret, resolve credentials, enable HTTP, expose a route, execute a connector, or authorize production.

## Declared intake

```text
telecom_ticketing_operator_sandbox_reference_intake
```

The intake remains scoped to:

```text
connector=telecom_ticketing_reference
environment=sandbox
access_mode=read
credential_profile=telecom_operations_api_reference
pilot=telecom_ticketing_read_only_sandbox_pilot
```

## Required operator inputs

R1 requires ten reference names:

1. `endpoint_reference`
2. `auth_method_reference`
3. `secret_provider_reference`
4. `tenant_reference`
5. `scope_reference`
6. `tls_policy_reference`
7. `allowlist_reference`
8. `security_review_reference`
9. `operator_approval_reference`
10. `kill_switch_reference`

These are registry or policy reference names. They are not URLs, credentials, tokens, certificates, or secret values.

## Intake states

| State | Meaning |
|---|---|
| `pending_operator_input` | No reference submission is present |
| `references_received_for_review` | Ten safe references were supplied for review |
| `blocked` | A forged or mismatched submission was detected |

`references_received_for_review` is not technical approval and does not activate a connector.

## Default-deny contract

```text
endpoint_registered=False
target_binding_created=False
secret_reference_registered=False
credentials_resolved=False
external_http_enabled=False
socket_access_enabled=False
request_execution_allowed=False
dispatcher_invocation_allowed=False
persistence_allowed=False
background_task_allowed=False
route_exposure_allowed=False
runtime_enabled=False
production_allowed=False
automatic_activation_allowed=False
```

The same flags remain false after safe references are received.

## Reference validation

Reference validation rejects empty strings, surrounding whitespace, URL schemes, authorization material, passwords, tokens, secrets, private keys, certificates, client secrets, API keys, and raw payload markers.

The module does not read environment-variable values. Operator inputs must later enter through a separately governed and authenticated workflow.

## No endpoint registration

`endpoint_reference` identifies a future controlled registry entry. R1 does not store or validate an endpoint URL.

The future target binding remains disabled until a separate phase verifies the operator-provided reference.

## No secret registration

`secret_provider_reference` identifies a future customer vault or secret-manager provider reference.

R1 does not accept a secret value and does not modify the existing secret-manager contract.

## No network or execution

R1 does not import or use HTTP clients, sockets, environment readers, filesystem persistence, asynchronous workers, dispatcher execution, runtime routes, or production connectors.

## Acceptance boundaries

A reference submission may become ready for reference review only when all ten fields are present and safe.

Reference review readiness does not imply:

- endpoint registration;
- DNS or TLS validation;
- allowlist activation;
- authentication validation;
- secret registration;
- credential resolution;
- network enablement;
- runtime approval;
- production approval.

## Testing

Tests cover the immutable registry, frozen contracts, required input names, pending assessment, received-for-review assessment, forged mismatch blocking, raw reference rejection, default-deny flags, absence of environment and network access, package exports, and documentation markers.

## Next phase

```text
EXTERNAL-CONNECTIVITY-16F-R2
Real secret-manager provider binding
```

R2 must not begin actual provider binding until an operator or customer supplies the required governed references and approvals.
