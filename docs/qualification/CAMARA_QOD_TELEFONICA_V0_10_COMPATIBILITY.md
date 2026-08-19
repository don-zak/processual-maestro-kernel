# CAMARA QoD v1.1.0 vs Telefonica QoD v0.10

## Purpose

This note records the compatibility boundary between the governed CAMARA QoD
v1.1.0 contract and the independently exercised Telefonica Open Gateway QoD
v0.10 sandbox/mock API.

It does **not** modify the approved CAMARA governance contract and does **not**
grant provider network, runtime connector, staging, or production authority.

## Governed CAMARA contract

- API version: `1.1.0`
- governance version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- approved operations:
  - `createSession` — `POST /sessions`
  - `getSession` — `GET /sessions/{sessionId}`
  - `deleteSession` — `DELETE /sessions/{sessionId}`
  - `extendQosSessionDuration` — `POST /sessions/{sessionId}/extend`
  - `retrieveSessionsByDevice` — `POST /retrieve-sessions`

## Telefonica external sandbox evidence

The retained execution evidence is:

`docs/qualification/evidence/TELEFONICA_QOD_CIBA_SESSION_LIFECYCLE_2026-08-19.json`

Observed successful external sandbox/mock calls:

- CIBA authorization: HTTP `200`
- token exchange: HTTP `200`
- create session: HTTP `201`
- get session: HTTP `200`
- delete session: HTTP `204`

Provider surface used by that execution:

- provider: Telefonica Open Gateway
- API version: `v0.10`
- sandbox base: `https://sandbox.opengateway.telefonica.com/apigateway/qod/v0`
- authorization: CIBA
- QoD purpose/scope: `dpv:RequestedServiceProvision#qod`

No raw client secret, access token, auth request ID, or session ID is retained in
public evidence.

## Compatibility assessment

| Operation | CAMARA v1.1.0 shape | Telefonica v0.10 shape | External proof | Status |
| --- | --- | --- | --- | --- |
| createSession | `POST /sessions` | `POST /sessions` | yes | semantic shape matches |
| getSession | `GET /sessions/{sessionId}` | `GET /sessions/{sessionId}` | yes | semantic shape matches |
| deleteSession | `DELETE /sessions/{sessionId}` | `DELETE /sessions/{sessionId}` | yes | semantic shape matches |
| extendQosSessionDuration | `POST /sessions/{sessionId}/extend` | `POST /sessions/{sessionId}/extend` | not yet retained | semantic shape matches, execution pending |
| retrieveSessionsByDevice | `POST /retrieve-sessions` | not present in exercised Telefonica v0.10 session surface | no | incompatible/unproven for exact contract |

The shared operation paths are evidence of partial interoperability only. The
provider API version and authorization scope differ from the governed CAMARA
v1.1.0 contract, and the governed contract contains an additional
`retrieveSessionsByDevice` operation not proven on this provider surface.

## Current qualification state

The project may truthfully project:

- `authenticated_sandbox_reachability_proven=true`
- `external_mock_sandbox_proven=true`
- proven external operations: `createSession`, `getSession`, `deleteSession`

The project must continue to project:

- `operator_network_qos_proven=false`
- `provider_sandbox_proven=false` for the governed CAMARA v1.1.0 contract
- `runtime_connector_approved=false`
- `production_allowed=false`

## Extend closure

`tools/telefonica_qod_ciba_extend_probe.ps1` performs a separate CIBA-authenticated
create → extend → get → delete lifecycle. A successful run may add
`extendQosSessionDuration` to the external mock interoperability evidence, but it
still cannot remove the version-mismatch or operator-network blockers.

## Remaining blockers

1. Execute and retain the Telefonica v0.10 extend proof.
2. Resolve or explicitly waive the absence of `retrieveSessionsByDevice` on the
   exercised provider surface; a waiver would require governance review and
   cannot be inferred from this evidence.
3. Obtain operator-network rather than mock-only QoS proof if provider sandbox
   qualification for the governed contract is required.
4. Approve and implement a runtime connector only after the exact provider
   compatibility contract is separately reviewed.
5. Production remains a separate authorization gate.
