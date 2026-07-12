# EXTERNAL-CONNECTIVITY-16G-R2

## Governed training customer-input review

Status: `ready_for_supervisor_review`

16G-R2 simulates receipt and review of the 27 reference inputs requested by
16G-R1. It validates the customer package locally and deterministically
without persistence, network access, credential resolution, task creation,
key issuance, sandbox launch, runtime activation, or production authority.

## Training purpose

The phase trains the customer integration officer and supervisor to:

- return approved reference names instead of raw secrets;
- detect missing and unexpected input fields;
- select a supported secret provider;
- select a supported TLS minimum version;
- distinguish package completeness from operational authorization;
- stop unsafe submissions before task or key creation;
- produce a review decision that can be audited in later phases.

Training reduces real integration risk by exercising the governed workflow
before endpoints, credentials, provider SDKs, allowlists, or certificates are
introduced.

## Supported review results

- `needs_clarification`: one or more required inputs are missing.
- `rejected_unsafe_input`: a selection, reference, or value is unsafe.
- `ready_for_supervisor_review`: all 27 references pass R2A and R3A checks.
- `blocked`: the schema or governed dependency is invalid.

`ready_for_supervisor_review` is not an activation approval.

## Reused contracts

The provider portion is projected through:

- `SecretProviderReferenceSubmission`
- `assess_secret_provider_binding_readiness`

The outbound portion is projected through:

- `OutboundAllowlistTlsReferenceSubmission`
- `assess_outbound_allowlist_tls_readiness`

The phase does not duplicate either readiness implementation.

## Supported training selections

Secret providers:

- `gcp_secret_manager`
- `hashicorp_vault`
- `aws_secrets_manager`
- `azure_key_vault`

TLS minimum versions:

- `tls_1_2`
- `tls_1_3`

## Safety boundary

Submission values are copied into an immutable mapping. Raw URLs, passwords,
tokens, client secrets, private keys, certificates, API keys, authorization
material, raw values, and raw payloads are rejected.

The following remain false:

- `customer_submission_persisted`
- `integration_task_created`
- `activation_permission_key_issued`
- `provider_binding_created`
- `credentials_resolved`
- `connection_attempted`
- `fake_transport_invoked`
- `sandbox_launched`
- `external_http_enabled`
- `socket_access_enabled`
- `runtime_enabled`
- `production_allowed`

No integration task is created in R2. No activation permission key is issued.
The deterministic fake sandbox transport is not invoked.

## Next phase

16G-R3 may create a training integration task only after a complete R2 review
has status `ready_for_supervisor_review`.

16G-R3 must reuse the existing integration task and one-time activation
permission key lifecycle. It must not create a parallel key system.

Key issuance remains a separate supervisor-governed action. Sandbox launch
and production authorization remain disabled.
