# CAMARA QoD Operator Sandbox PowerShell Qualification R1

This runbook executes the reference-only CAMARA QoD operator-sandbox boundary with `tools/camara_qod_operator_sandbox_qualify.ps1`.

## Safety boundary

- PowerShell 7.2+ is required.
- Dry-run is the default; no provider request is sent unless `-ExecuteLive` is present.
- Base URL and credential material are resolved from environment variables by **name**.
- Do not place bearer tokens, client secrets, API keys, certificates, private keys, or raw provider responses in the request-plan JSON or command line.
- The script writes only sanitized evidence hashes/metadata; it does not retain raw request or response bodies.
- A successful sandbox run does not grant `runtime_connector_approved` or `production_allowed`.

## 1. Create request plan

Create a local file outside version control, for example `camara-request-plan.json`:

```json
{
  "governance_version": "camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee",
  "source_revision": "9cb179fd3b63f43d564c76689295cd681e723548",
  "operations": [
    {
      "operation_id": "createSession",
      "method": "POST",
      "path": "/sessions",
      "approval_reference": "change-approval-camara-qod-sandbox-001",
      "body_file": "create-session.json"
    },
    {
      "operation_id": "getSession",
      "method": "GET",
      "path": "/sessions/{sessionId}"
    },
    {
      "operation_id": "extendQosSessionDuration",
      "method": "POST",
      "path": "/sessions/{sessionId}/extend",
      "approval_reference": "change-approval-camara-qod-sandbox-001",
      "body_file": "extend-session.json"
    },
    {
      "operation_id": "deleteSession",
      "method": "DELETE",
      "path": "/sessions/{sessionId}",
      "approval_reference": "change-approval-camara-qod-sandbox-001"
    }
  ]
}
```

`retrieveSessionsByDevice` may be added as a separate read-semantic POST using a body file.

If the provider does not return a top-level `sessionId` from `createSession`, set a safe `session_id` on the later path-based operations.

## 2. Create request body files

Keep request bodies in the same local directory as the request plan. Example `create-session.json`:

```json
{
  "duration": 60,
  "qosProfile": "<provider-approved-sandbox-profile>",
  "device": {
    "phoneNumber": "<provider-approved-test-identity>"
  },
  "applicationServer": {
    "ipv4Address": "<provider-approved-test-application-server>"
  }
}
```

Use only provider-approved sandbox fixtures. The exact request shape must match the operator's CAMARA QoD implementation and the reviewed subject-mode rules. Do not put OAuth tokens, client secrets, API keys, private keys, or certificate material in these JSON files.

## 3. Configure endpoint and auth references

### Bearer token reference

```powershell
$env:CAMARA_SANDBOX_BASE_URL = 'https://<operator-sandbox-host>/<qod-base-path>'
$env:CAMARA_BEARER_TOKEN = '<resolved sandbox token>'
```

The variable values are local secret/environment material; only the variable names are passed to the script.

### OAuth client credentials

```powershell
$env:CAMARA_SANDBOX_BASE_URL = 'https://<operator-sandbox-host>/<qod-base-path>'
$env:CAMARA_TOKEN_URL = 'https://<operator-auth-host>/<token-path>'
$env:CAMARA_CLIENT_ID = '<sandbox client id>'
$env:CAMARA_CLIENT_SECRET = '<sandbox client secret>'
```

## 4. Dry run first

Bearer-token example:

```powershell
pwsh ./tools/camara_qod_operator_sandbox_qualify.ps1 `
  -BaseUrlEnvVar CAMARA_SANDBOX_BASE_URL `
  -AuthMode BearerTokenReference `
  -BearerTokenEnvVar CAMARA_BEARER_TOKEN `
  -RequestPlanPath ./camara-request-plan.json `
  -EvidenceDirectory ./camara-operator-evidence
```

A passing dry run ends with:

```text
QUALIFICATION PRECHECK: PASS
No network request was executed.
```

## 5. Execute the authorized operator sandbox

Only after the dry run passes and the operator sandbox endpoint/credentials are authorized:

```powershell
pwsh ./tools/camara_qod_operator_sandbox_qualify.ps1 `
  -BaseUrlEnvVar CAMARA_SANDBOX_BASE_URL `
  -AuthMode BearerTokenReference `
  -BearerTokenEnvVar CAMARA_BEARER_TOKEN `
  -RequestPlanPath ./camara-request-plan.json `
  -EvidenceDirectory ./camara-operator-evidence `
  -ExecuteLive
```

OAuth client-credentials example:

```powershell
pwsh ./tools/camara_qod_operator_sandbox_qualify.ps1 `
  -BaseUrlEnvVar CAMARA_SANDBOX_BASE_URL `
  -AuthMode OAuthClientCredentials `
  -TokenUrlEnvVar CAMARA_TOKEN_URL `
  -ClientIdEnvVar CAMARA_CLIENT_ID `
  -ClientSecretEnvVar CAMARA_CLIENT_SECRET `
  -OAuthScope 'quality-on-demand:sessions:create quality-on-demand:sessions:read quality-on-demand:sessions:update quality-on-demand:sessions:delete' `
  -RequestPlanPath ./camara-request-plan.json `
  -EvidenceDirectory ./camara-operator-evidence `
  -ExecuteLive
```

## 6. Evidence

The script writes:

`camara-qod-operator-sandbox-summary.json`

The evidence includes the exact governance/source versions, provider host and observed DNS addresses, auth mode, operation/method metadata, HTTP statuses, elapsed times, and SHA-256 digests of request/response bodies. It deliberately does not retain raw bodies or credential values.

A successful live run may set:

- `provider_network_proof=true`;
- `provider_sandbox_proven=true`.

It remains:

- `runtime_connector_approved=false`;
- `production_allowed=false`.

## Expected next step

After a successful live sandbox run, retain the sanitized evidence and review it before any separate runtime connector-approval decision. Production remains independently gated.