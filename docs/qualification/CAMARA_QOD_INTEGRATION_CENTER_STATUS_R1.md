# CAMARA-QOD-INTEGRATION-CENTER-STATUS-R1

## Purpose

Record the safe server-owned status projection and Integration Center UI contract for the reviewed CAMARA Quality on Demand qualification work.

This stage improves operator visibility. It does **not** register a QoD runtime task, approve a connector, prove a provider sandbox, execute the manual public-source live workflow, or grant production authority.

## Safe admin status route

The Settings admin router exposes:

`GET /settings/admin/integration-center/camara-qod-qualification`

The route requires authenticated administrator qualification-read authority. Unauthenticated requests remain `401`; users without the required admin read scope remain `403`.

The response projects only review-safe state:

- reviewed source identity, repository, immutable revision and root path;
- API version;
- whether the deployment-owned trusted-source catalog exactly enables the reviewed source policy tuple;
- proposal-only semantic mapping and the five reviewed outbound operations;
- callback operations excluded from outbound binding;
- explicit negative provider/runtime/production authority fields.

It does not return API documents, raw bundle documents, access tokens, client secrets, raw API keys, provider credentials, or secret values.

An invalid trusted-source catalog fails closed with `503 trusted_source_catalog_invalid` rather than rendering a misleading disabled/enabled state.

## Exact server policy enablement

`server_trusted_source_enabled=True` requires an exact match with the reviewed candidate across:

- source identity;
- repository;
- contract family;
- exact approved revisions;
- root path prefixes;
- reference path prefixes;
- policy version.

Near matches remain disabled. Tests cover contract-family drift, policy-version drift, and widened reference-prefix policy.

This field represents source-acquisition policy enablement only. It does not imply that the source was live-fetched, that semantic tasks are runtime-registered, or that an operator sandbox is available.

## Route-backed Integration Center

`admin_integration_center_18.js` now requests the safe CAMARA status route alongside existing readiness/case/handoff/progress routes.

The CAMARA card derives intermediate state from the server projection:

- server trusted-source policy: `Policy enabled` only for the exact server policy tuple;
- semantic task mapping: `Reviewed proposal` only when the server projection reports `proposal_only` with five reviewed outbound operations;
- live source acquisition: remains `Not proven` unless the server projection explicitly reports retained evidence;
- live operator sandbox: remains `Blocked` unless provider sandbox proof is explicitly reported;
- production: always remains `Blocked` in this qualification UI.

If the CAMARA status route fails or is unavailable, the card does not disappear and does not infer success. It renders a conservative fallback that keeps trusted-source enablement, live acquisition, provider sandbox and runtime authority unproven, while retaining only the reviewed pinned candidate metadata.

The immediate-priority copy now reflects actual progress: semantic mapping is no longer described as missing. The next governance step is review/registration of dedicated QoD task, entitlement and quota contracts. No registration occurs in this stage.

## UI/UX and accessibility boundary

The existing Integration Center accessibility contracts remain intact:

- `tablist` / `tab` / `tabpanel` semantics;
- `aria-selected`, `aria-controls`, `aria-labelledby`;
- roving `tabindex`;
- ArrowLeft / ArrowRight / Home / End keyboard navigation;
- loading `role=status`;
- partial-route failure `role=alert`;
- responsive platform/readiness layout and reduced-motion CSS remain unchanged.

The loading copy now includes CAMARA qualification status so users understand that standards readiness is part of the route-backed loading state.

This remains static contract/accessibility qualification. Rendered browser visual QA in the real application runtime is still outstanding.

## CI evidence

Implementation head:

`308037d20ccc3c8a0eb76b85a85a5f8372e02b9e`

`CAMARA Public Source Contracts` run `#19` (`32212885698`) completed successfully and covered:

- public-source runner contracts;
- semantic mapping and drift gates;
- safe CAMARA status-route authentication/fail-closed behavior;
- exact catalog policy enablement and near-match rejection;
- route-backed Integration Center static contracts;
- accessibility and no-secret UI assertions;
- trusted source acquisition/bundle regressions.

Artifact:

- ID `9351355353`;
- digest `sha256:a7a6e79294fbb061562963058ded7513c736e363503bf9fb7c943e4e1fad9c0f`.

`Sandbox Integration Qualification` run `#157` (`32212885770`) completed successfully on the same implementation head across PostgreSQL/Redis checks, clean Alembic, focused Ruff, focused regression tests, evidence upload and cleanup.

Artifact:

- ID `9351364439`;
- digest `sha256:f93e4f3d98f22e2ae05eb79b6018d69e4684d719b918674fddff906d311aeced`.

Routine CI still records:

- `trusted_source_live_fetch=false`;
- `production_credentials=false`;
- `external_provider_credentials=false`;
- `external_provider_network_proof=false`;
- `runtime_connector_approved=false`;
- `production_allowed=false`.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: route-backed review visibility is now CI-proven, but the manual live public-source workflow has not been executed, dedicated QoD runtime task/entitlement/quota contracts are not registered, no provider/operator sandbox credentials or endpoint proof exists, and rendered browser/external-client E2E qualification remains outstanding.
