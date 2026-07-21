# Stage 18 — Supervisor to Enterprise Credential Flow

## Security chain

1. Admin authentication.
2. Supervisor Session Key.
3. Enterprise case automated validation.
4. Supervisor qualification decision.
5. Enterprise Qualification Grant.
6. Enterprise grant activation.
7. Executable-task eligibility.
8. Task-scoped sandbox API key.
9. Usage, rotation, expiration, and revocation.

## Key separation

### Supervisor Session Key

- Internal supervisor authority.
- Required for protected supervisor writes.
- Never delivered to the enterprise client.
- Never embedded in a qualification grant.
- Never used as an API execution credential.

### Qualification Grant

- Case-scoped authorization record.
- Approves selected executable tasks only.
- Does not execute an API.
- Does not contain a raw secret.
- Sandbox-only in Stage 18.

### Task-scoped API key

- Bound to one client, case, task, grant, and operational profile.
- Issued only after grant validation.
- Raw value visible once at issuance.
- Stored as a hash and safe metadata.
- Rotatable, revocable, expiring, and auditable.

## Default-deny invariants

- `production_allowed=false`
- `runtime_connector_approved=false`
- `write_allowed=false`
- `restricted_allowed=false`
- `external_http_allowed=false`
- `raw_secret_visible=false`
- no arbitrary scopes
- no cross-client issuance
- no cross-case issuance
- no credential for reference-only tasks

## Executable tasks

### CAMARA

- `sandbox_capability_probe`
- profile: `camara_sandbox_read_probe`

### TM Forum

- `ctk_contract_probe`
- profile: `tmforum_sandbox_contract_probe`

### Operator-specific

- `callback_delivery_probe`
- profile: `operator_sandbox_callback_probe`

All existing intake tasks remain reference, evidence, configuration, or
review tasks and do not receive API credentials.

## UI sequence

### Supervisor Integration Center

1. Supervisor authority status.
2. Qualification review queue.
3. Case evidence and blocker summary.
4. Select executable tasks.
5. Approve, request revision, or reject.
6. Grant lifecycle summary.
7. Task credential lifecycle summary.

### Enterprise Workspace

1. Intake tasks.
2. Automated validation.
3. Supervisor review status.
4. Qualification grant status.
5. Eligible executable tasks.
6. Issue, rotate, or revoke task key.
7. Safe usage metadata.

## Stage boundaries

This contract stage does not:

- issue keys;
- store raw keys;
- activate external HTTP;
- approve production;
- approve runtime connectors;
- change supervisor RBAC;
- change the current client case API.