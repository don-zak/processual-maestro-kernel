# Telefonica QoD `retrieveSessionsByDevice` compatibility decision — 2026-08-19

## Decision

For the currently documented Telefonica Open Gateway QoD v0.10 surface, `retrieveSessionsByDevice` is classified as **not exposed / not externally provable on this provider surface**.

This is a provider-compatibility finding, not a modification or waiver of the governed CAMARA QoD v1.1.0 contract.

## Governed contract requirement

The pinned CAMARA QoD v1.1.0 semantic contract includes the outbound operation:

```text
retrieveSessionsByDevice
POST /retrieve-sessions
→ camara.qod.sessions_retrieve_by_device
```

It remains one of the five approved governed task bindings.

## Provider reference reviewed

The current Telefonica Open Gateway documentation index (`llms.txt`) enumerates the QoD v0.10 API reference operations as:

- Get all QoS profiles v0.10
- Get QoS profile for a given name v0.10
- Create QoD session v0.10
- Check QoD session v0.10
- Cancel QoD session v0.10
- Extend a QoD session v0.10

The indexed QoD v0.10 reference contains no `retrieveSessionsByDevice` operation and no `/retrieve-sessions` endpoint.

Reference reviewed on 2026-08-19:

```text
https://developers.opengateway.telefonica.com/llms.txt
```

Relevant current index range: QoD entries corresponding to the six operations above.

## Qualification effect

The Telefonica surface therefore has four externally exercised governed operation shapes:

```text
createSession                 proven positive-path interoperability
getSession                    proven positive-path interoperability
 deleteSession                 proven positive-path interoperability
extendQosSessionDuration      proven positive-path interoperability
```

`retrieveSessionsByDevice` remains unavailable on the reviewed Telefonica v0.10 surface.

Additionally, `getSession` negative-path behavior has a confirmed sandbox/mock divergence: a fresh UUID that was never created returned HTTP 200 while the provider reference documents HTTP 404 for session-not-found.

The compatibility result remains:

```text
compatibility_state=partial_interoperability_with_negative_path_divergence
provider_sandbox_proven=false
governed_camara_v1_1_provider_sandbox_proven=false
operator_network_qos_proven=false
runtime_connector_approved=false
staging_allowed=false
production_allowed=false
```

## Governance consequence

No automatic compatibility waiver is granted.

Before a provider-specific connector can be approved, governance must explicitly choose one of the following paths:

1. Require an exact/current provider surface that exposes all five governed CAMARA QoD v1.1.0 operations and meets required failure semantics.
2. Approve a provider-specific Telefonica adapter profile with an explicitly reduced capability set, while keeping `retrieveSessionsByDevice` unavailable and preserving the immutable governed CAMARA contract separately.
3. Defer Telefonica connector qualification and use the current v0.10 result only as external mock interoperability evidence.

Until such a decision is recorded, the project must remain fail-closed for provider connector authority.

## Security and evidence boundary

No provider secret, access token, auth request ID, session ID, or customer identifier is required or retained by this decision record.
