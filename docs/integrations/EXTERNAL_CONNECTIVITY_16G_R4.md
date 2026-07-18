# EXTERNAL-CONNECTIVITY-16G-R4 — Reference-only secret-provider binding simulation

## Status and purpose

16G-R4 is a governed, isolated, reference-only simulation. It demonstrates
how accepted 16G-R2 customer references can be projected into the existing
16F-R2A secret-provider readiness assessment after an existing pilot task and
Activation Permission Key have been validated.

It does not create a real provider binding and does not authorize R2B or R3B
real connectivity.

## Reused contracts

R4 reuses, without creating parallel systems:

- `TrainingCustomerInputSubmission` and `TrainingCustomerInputReview`;
- `TrainingActivationIsolation`;
- `SecretProviderReferenceSubmission`;
- `assess_secret_provider_binding_readiness`;
- `create_integration_task`;
- `issue_activation_permission_key`;
- `validate_activation_permission_key`;
- `control_integration_task`.

The supported training provider references are:

- GCP Secret Manager;
- HashiCorp Vault;
- AWS Secrets Manager;
- Azure Key Vault.

No provider SDK is imported or initialized.

## Read-only key validation

`validate_activation_permission_key` reads the isolated task store and performs
no store write and no audit write. It requires:

- a persisted task;
- status `activation_permission_issued`;
- `integration_key_revoked=false`;
- a stored key identifier and hash;
- a valid timezone-aware future expiry;
- a provided key identifier matching the stored identifier;
- a provided key hash matching through constant-time comparison.

Forged, malformed, expired, suspended, resumed, revoked, and cancelled keys
are default-deny. The raw key and stored hash are never returned.

## Reference projection

R4 maps seven validated R2 provider references into
`SecretProviderReferenceSubmission`:

- provider reference;
- authentication-method reference;
- rotation-policy reference;
- customer-authorization reference;
- operator-approval reference;
- security-review reference;
- revocation-policy reference.

The canonical R2 review is recomputed from the supplied immutable submission.
A mismatched or forged review is rejected before any training store or audit
file is created.

The assessment may reach
`provider_references_received_for_review`, but this means review readiness
only. It does not mean a provider client or binding exists.

## Simulation lifecycle

The isolated sequence is:

1. Verify the canonical supervisor-ready R2 review.
2. Create a training-only pilot task.
3. Issue an Activation Permission Key once.
4. Validate the key against persisted state.
5. Build the seven-field reference submission.
6. Run the existing provider-readiness assessment.
7. Produce synthetic, non-persisted simulation metadata.
8. Revoke the task and key.
9. Restore caller environment paths in `finally`.

Any failure after task creation triggers revocation in `finally`.

## Default-deny result

Every R4 simulation preserves:

- `provider_binding_created=false`
- `provider_client_initialized=false`
- `secret_reference_registered=false`
- `secret_value_accessed=false`
- `secret_value_stored=false`
- `raw_secret_visible=false`
- `authentication_performed=false`
- `credentials_resolved=false`
- `resolution_allowed=false`
- `external_http_enabled=false`
- `socket_access_enabled=false`
- `persistence_allowed=false`
- `background_task_allowed=false`
- `route_exposure_allowed=false`
- `runtime_enabled=false`
- `production_allowed=false`
- `automatic_activation_allowed=false`

There is no secret resolution, no authentication, no external HTTP, no DNS,
no socket, no TLS context, and no provider SDK. There is no connector
dispatch, no sandbox launch, and no production activation.

## Persistence and leakage boundary

Only the existing isolated pilot task and its safe audit events are persisted.
The provider submission and assessment are not written to the task store or
audit. The raw Activation Permission Key is transient, is excluded from the
result model, and is absent from store and audit.

The final task status is always `revoked` after a successful simulation. An
aborted simulation also attempts revocation before restoring the environment.

## Next phase

16G-R5 may simulate outbound allowlist and TLS approval using accepted R2
references. It must not resolve DNS, open a socket, create a TLS context, use
real certificates, or loosen any existing network, runtime, or production
guardrail.
