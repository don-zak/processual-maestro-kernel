# Integration Onboarding 13A — Supervisor-Issued Integration Claim Keys

Status: `draft_review`

## Purpose

13A adds supervisor-issued Integration Claim Keys. These keys are onboarding claims only.
They do not enable production, runtime connectors, external HTTP, or raw secret visibility.

## Core rule

```text
API key does not equal external runtime approval.
Integration Claim Key does not enable production.
Integration Claim Key does not enable runtime connector.
Integration Claim Key does not enable external HTTP.
Integration Claim Key does not expose raw secrets.
```

## Admin flow

```text
1. Supervisor issues Integration Claim Key.
2. Raw claim key is visible once in the issue response.
3. List view shows masked keys only.
4. Supervisor can revoke claim keys.
5. Admin write actions require supervisor session and allowed supervisor scope.
```

## Client flow

```text
1. Operator integration officer pastes claim key in Settings.
2. Backend validates the key.
3. Backend creates onboarding case.
4. Backend returns required operator inputs.
5. Runtime and production remain blocked.
```

## Endpoints

```text
POST /settings/admin/integration-claim-keys
GET  /settings/admin/integration-claim-keys
POST /settings/admin/integration-claim-keys/{claim_key_id}/revoke
POST /settings/client/integration-claim-keys/redeem
GET  /settings/client/integration-onboarding/status
```

## Required operator inputs

```text
operator_api_documentation_reference
sandbox_endpoint_reference
auth_method_reference
allowed_scopes_matrix
rate_limit_policy
test_account_reference
incident_escalation_path
production_approval_path
```

## Guardrails

```json
{
  "runtime_enabled": false,
  "production_allowed": false,
  "external_http_enabled": false,
  "raw_secret_visible": false
}
```

## Audit events

```text
integration_claim_key_issued
integration_claim_key_redeemed
integration_claim_key_revoked
```

## Production rule

Production access remains blocked until a separate production gate, customer endpoint binding approval,
runtime connector approval, security review, and operator sign-off exist.
