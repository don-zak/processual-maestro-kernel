# EXTERNAL-CONNECTIVITY-16G-R7

## Status

Implemented locally on branch:

`pmk-external-connectivity-16g-r7`

Baseline:

`14712b1fd0c3e4c11cf53e2393fc90ef80d287f5`

## Purpose

R7 aligns the declared OpenAPI request-body contracts with the runtime
behavior of Integration Pilot task write routes.

Before R7, six routes manually called `await request.json()` without a
FastAPI body field or an OpenAPI `requestBody`. A missing or malformed body
could therefore escape normal validation and produce HTTP 500.

## Affected routes

- `POST /settings/admin/integration-tasks`
- `POST /settings/admin/integration-tasks/{task_id}/suspend`
- `POST /settings/admin/integration-tasks/{task_id}/resume`
- `POST /settings/admin/integration-tasks/{task_id}/revoke`
- `POST /settings/admin/integration-tasks/{task_id}/cancel`
- `POST /settings/admin/integration-tasks/{task_id}/activation-permission-key`

The existing route below was inventoried and retained unchanged:

- `POST /settings/admin/supervisor-session-keys/{session_key_id}/revoke`

Its body remains required and uses
`SupervisorSessionKeyRevokeRequest`.

## Request models

R7 declares:

- `PMK13BIntegrationTaskCreateRequest`
- `PMK13BIntegrationTaskControlRequest`
- `PMK13BActivationPermissionKeyIssueRequest`

Create and activation models preserve additional existing payload fields.
The control model declares optional `reason` with an empty-string default.

## Contract decision

For the six Integration Pilot task writes:

- the JSON request body is optional;
- a missing body is equivalent to `{}`;
- `{}` preserves the existing default-deny behavior;
- malformed JSON returns HTTP 422;
- malformed JSON does not invoke a service write;
- OpenAPI declares `application/json`;
- all downstream payload fields remain available;
- actor derivation remains based on the validated supervisor session;
- supervisor-session guard behavior is unchanged.

## Security invariants

R7 does not grant runtime or external authority.

The following remain false unless a separate governed phase explicitly
changes them:

- `production_allowed`
- `runtime_connector_approved`
- `external_http_allowed`
- `automatic_activation_allowed`
- `credentials_storage_allowed`
- `action_execution_allowed`
- `raw_secret_visible`

R7 does not:

- resolve credentials;
- contact a secret provider;
- perform DNS resolution;
- open sockets;
- perform external HTTP;
- activate a production connector;
- expose raw supervisor or activation keys.

## Regression coverage

`tests/test_integration_task_request_body_contract_16g_r7.py` covers:

- OpenAPI body declaration for all six routes;
- missing-body create behavior;
- missing-body suspend, resume, revoke, and cancel behavior;
- missing-body activation-key issuance behavior;
- malformed JSON returning 422 without a service write;
- preservation of the existing typed Supervisor Session revoke contract.

The pre-fix regression state was:

`8 failed, 1 passed`

The direct post-fix state was:

`9 passed`

## Acceptance criteria

- `no_empty_body_500=True`
- `malformed_json_returns_422=True`
- `openapi_runtime_contract_match=True`
- `validation_failures_side_effect_free=True`
- `default_deny_preserved=True`
- `supervisor_revoke_contract_preserved=True`
- `raw_secret_exposure=0`
- `repository_data_preserved=True`
- `full_suite_passed=True`
