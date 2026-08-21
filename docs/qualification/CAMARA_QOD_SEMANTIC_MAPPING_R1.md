# CAMARA-QOD-SEMANTIC-MAPPING-R1

## Purpose

Record the reviewed semantic mapping boundary for the pinned CAMARA Quality on Demand r3.2 / API v1.1.0 source without registering an executable Maestro task or connector.

This stage answers a narrower question than provider sandbox qualification: which reviewed CAMARA operations and scopes correspond to which proposed Maestro task semantics, data classifications, entitlement concepts, and quota meters?

## Immutable source

The mapping is bound to:

- source identity: `camara.quality_on_demand.r3_2`;
- repository: `camaraproject/QualityOnDemand`;
- revision: `9cb179fd3b63f43d564c76689295cd681e723548`;
- path: `code/API_definitions/quality-on-demand.yaml`;
- API version: `1.1.0`.

The reviewed outbound operation inventory is:

1. `createSession` — `POST /sessions` — `quality-on-demand:sessions:create`;
2. `getSession` — `GET /sessions/{sessionId}` — `quality-on-demand:sessions:read`;
3. `deleteSession` — `DELETE /sessions/{sessionId}` — `quality-on-demand:sessions:delete`;
4. `extendQosSessionDuration` — `POST /sessions/{sessionId}/extend` — `quality-on-demand:sessions:update`;
5. `retrieveSessionsByDevice` — `POST /retrieve-sessions` — `quality-on-demand:sessions:retrieve-by-device`.

`postNotification` is a provider-to-consumer callback nested under `createSession`. It is explicitly excluded from Maestro outbound endpoint binding.

## Why `network_assurance` is not reused

The existing `network_assurance` adapter contract is read-only operational diagnostics. It has no optional write scope and explicitly restricts `network:write`.

QoD `createSession`, `deleteSession`, and `extendQosSessionDuration` change network service state. Mapping them to the existing read-only assurance task family would erase an important authorization and approval boundary.

The reviewed mapping therefore proposes a separate QoD task family but deliberately leaves every proposed task unregistered:

- `camara.qod.session_create` — approval-gated write;
- `camara.qod.session_get` — read;
- `camara.qod.session_delete` — approval-gated write;
- `camara.qod.session_extend` — approval-gated write;
- `camara.qod.sessions_retrieve_by_device` — read despite HTTP POST, because POST is used for sensitive/complex device input rather than mutation.

For every mapping:

- `runtime_task_registered=False`;
- `runtime_connector_approved=False`;
- `production_allowed=False`.

## Canonical input and identity rules

`createSession` requires the canonical concepts `application_server`, `qos_profile`, and `duration_seconds`. Device identifiers, port selectors, notification sink, and managed notification credential reference are optional/conditional inputs.

The mapping records token-subject rules explicitly:

- two-legged access requires a device where the CAMARA contract requires subject identification;
- three-legged access identifies the subject from the token and forbids duplicate caller device identification where specified;
- notification sink credentials must be represented by managed credential references, not raw secrets in task state.

`retrieveSessionsByDevice` remains a read semantic even though the API uses POST. The device input is conditional: required for two-legged subject resolution and omitted for three-legged subject resolution.

## Data classification boundary

The mapping flags data categories needed for later entitlement/privacy review, including:

- network identifiers;
- session identifiers;
- application endpoints;
- network service state/control;
- device identifiers that may constitute personal data.

These labels are qualification metadata. They do not by themselves grant a data entitlement or provider credential.

## Proposed entitlement and quota concepts

The mapping records review candidates such as:

- `camara_qod_session_read`;
- `camara_qod_session_manage`;
- per-operation quota meters for create/read/delete/update/retrieve-by-device.

These identifiers are proposals only. They are not added to the authoritative plan/entitlement/quota catalogs in this stage.

## Semantic drift gate

`assess_camara_qod_semantic_alignment()` compares discovery output to the reviewed mapping and fails closed on:

- missing expected operations;
- newly appearing unreviewed outbound operations;
- duplicate/missing operation IDs;
- HTTP method drift;
- path drift;
- OAuth/OpenID scope drift.

The public-source qualification runner requires all of the following before returning `public_source_qualification_ready=True`:

1. discovery quality passes;
2. trusted relative references are fully resolved;
3. exact source identity attestation succeeds;
4. semantic mapping is exactly aligned.

Even then, the returned evidence fixes runtime/production/provider authority to false.

## Focused CI evidence

On implementation head `b9d5389e59bef3af49e9a522c0266636f3567c86`:

- `CAMARA Public Source Contracts` run `#8` (`32212331804`) passed Ruff and all public-source/semantic/trusted-source tests.
- Evidence artifact: `9351171026`.
- Artifact digest: `sha256:410b09899e989fd4ced81b766ace9e21658bef33c919f1c3a25fe306f620c2a7`.
- `Sandbox Integration Qualification` run `#146` (`32212331765`) also completed successfully across PostgreSQL/Redis checks, clean Alembic, focused Ruff, regression tests, evidence upload, and cleanup.
- Regression artifact: `9351179392`.
- Regression artifact digest: `sha256:e8ea7f054b754be94943fdaacbf2668a41a1b241629b5e04ebf1f21c820c694e`.

The specialized CI evidence retains:

- `camara_qod_network_assurance_reuse=false`;
- `camara_qod_runtime_task_registered=false`;
- `trusted_source_live_fetch=false`;
- `external_provider_credentials=false`;
- `external_provider_network_proof=false`;
- `runtime_connector_approved=false`;
- `production_allowed=false`.

## Gate state

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: the immutable source contract, relative-reference bundling, reviewed QoD semantic map, and semantic drift gate are CI-proven. The manual live public-source workflow has not yet been executed as qualification evidence, the proposed Maestro tasks/entitlements are not runtime-registered, and no operator/provider sandbox endpoint, credentials, or request/response proof exists.
