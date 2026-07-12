# EXTERNAL-CONNECTIVITY-16G-R1

## Governed training connection request

Status: `input_package_ready_for_customer`

16G-R1 simulates preparation of a realistic telecom ticketing sandbox
connection request. It produces a deterministic customer-facing package of
reference inputs. It performs no real binding or connection.

The governed identifiers are:

- request: `telecom_ticketing_training_connection_request`
- package: `telecom_ticketing_training_customer_input_package`
- connector: `telecom_ticketing_reference`
- environment: `sandbox`
- access mode: `read`

## Customer package

The package is addressed to the `customer_integration_officer`. It requests
27 governed inputs:

- 15 secret-provider and authorization references;
- 12 outbound allowlist and TLS references.

Candidate providers are GCP Secret Manager, HashiCorp Vault, AWS Secrets
Manager, and Azure Key Vault. Candidate minimum TLS versions are TLS 1.2 and
TLS 1.3.

Every requested item is required, reference-only, and marked
`raw_value_prohibited=true`.

The customer must not send passwords, tokens, API keys, client secrets,
private keys, certificates, authorization headers, raw secret values, raw
payloads, production credentials, or production endpoints.

## Workflow boundary

The package is ready to be sent for training review, but no customer
submission has been received. Completion of the package will be handled by a
later phase and remains subject to supervisor and operator review.

16G-R1 does not:

- create an integration task;
- issue an activation permission key;
- bind a secret provider;
- resolve a credential;
- apply an allowlist;
- create a TLS context;
- attempt a connection;
- invoke the deterministic fake transport;
- launch a sandbox;
- create an evidence bundle;
- persist a submission;
- expose a route;
- enable runtime;
- authorize production;
- perform automatic activation.

The following remain false:

- `customer_submission_received`
- `integration_task_created`
- `activation_permission_key_issued`
- `provider_binding_created`
- `credentials_resolved`
- `allowlist_applied`
- `tls_context_created`
- `connection_attempted`
- `fake_transport_invoked`
- `sandbox_launched`
- `evidence_bundle_created`
- `external_http_enabled`
- `socket_access_enabled`
- `route_exposure_allowed`
- `runtime_enabled`
- `production_allowed`
- `automatic_activation_allowed`

## Later training phases

16G-R2 will simulate receipt and governed review of a completed reference
package.

16G-R3 will reuse the existing integration task and activation permission key
lifecycle. It will not create a parallel key system.

16G-R6 will reuse the existing deterministic local fake sandbox transport. It
will not create a parallel transport or external HTTP connection.

Sandbox evidence will reuse the existing evidence builder. Production will
remain blocked after the training exercise.
