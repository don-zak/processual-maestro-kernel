# ENDPOINT-DISCOVERY-AND-CAMARA-SANDBOX-R1

## Purpose

Establish a fail-closed qualification boundary for discovering external API
operations before creating Enterprise endpoint bindings, and define what is
actually required before CAMARA, TM Forum, proprietary, or generic Enterprise
platforms can be called from the Maestro sandbox.

## Current repository capability

The repository has a governed discovery/binding/execution chain:

1. `integration_task_catalog.py` defines provider-neutral Maestro tasks and canonical inputs.
2. `endpoint_discovery_quality.py` inventories parsed OpenAPI/Swagger contracts and blocks unsafe or incomplete discovery results.
3. `endpoint_binding_provenance.py` requires verified immutable-source metadata, binds one exact operation to a secret-free binding fingerprint, and detects drift.
4. `endpoint_source_attestation.py` keeps immutable content pinning separate from publisher/source identity and only verifies identity when an exact source tuple matches a server-maintained trusted record.
5. `enterprise_endpoint_bindings.py` binds an external operation to a canonical task, adapter contract, credential profile, scopes, request parameters, response mapping, allowed status codes, and timeout.
6. `enterprise_endpoint_request_mapping.py` maps canonical task inputs into JSON request bodies without allowing arbitrary canonical fields.
7. `enterprise_sandbox_execution.py` performs governed HTTPS execution with redirect blocking, DNS resolution, public-address enforcement, `trust_env` disabled, response-size limits, JSON-only response handling, transient credentials, mapping validation, task-injection evidence, and explicit non-production posture.
8. `settings_endpoint_discovery_qualification_runtime.py` re-runs discovery assessment server-side, derives immutable source pin status instead of trusting caller booleans, attaches server-owned source-identity attestation, stores only safe provenance metadata, and reports changed bindings as `drifted`.
9. `sandbox_operational_readiness.py` requires binding, mapping, customer-scoped secret reference, non-production content contract, hardened live proof, and provisioning fingerprint before reporting `sandbox_ready`.

This is a qualification foundation. It is not provider connectivity or production authority.

## Endpoint extraction quality gate

`endpoint_discovery_quality.py` inventories:

- OpenAPI 3.0, OpenAPI 3.1, or Swagger 2.0 dialect;
- title and API version;
- operation IDs and duplicates;
- HTTP method and path;
- required path-parameter declarations;
- declared security schemes and OAuth/security scopes;
- undefined security-scheme references;
- request and response media types;
- response status contracts;
- external `$ref` dependencies;
- server/base-path hints;
- canonical SHA-256 of the supplied contract.

Binding generation is blocked for unpinned input, missing/duplicate `operationId`, invalid path parameters, undefined security schemes, unresolved external references, or missing response contracts.

Swagger 2.0 correctly inherits root-level `consumes` and `produces` when an operation does not override them. Operation-level media declarations override the root defaults. Security requirements must reference definitions present under OpenAPI `components.securitySchemes` or Swagger `securityDefinitions`.

CAMARA adds OpenAPI 3, non-WIP version, `x-camara-commonalities`, and versioned-server requirements.

## Path composition hardening

`enterprise_endpoint_bindings.build_request_preview()` percent-encodes each task-derived path value as one path segment and rejects unresolved placeholders. Regression coverage includes `/`, `?`, `#`, dot-segment input, already encoded separators, Unicode values, and ordinary identifiers.

This prevents canonical task values from changing the intended route shape after binding validation.

## Verified source provenance boundary

The Settings discovery route no longer trusts `release_pinned=True` or `external_references_resolved=True` as authority. Those legacy fields remain parseable only for transition compatibility and do not grant qualification.

Server-side pin derivation accepts two source forms:

- `artifact_sha256`: the supplied source revision must equal the canonical SHA-256 computed from the submitted API description;
- `git_commit`: the revision must be a 40–64 character hexadecimal commit digest and must appear in the supplied source reference.

The resulting provenance record stores:

- source reference;
- canonical source SHA-256;
- source kind;
- source revision;
- `source_pin_verified=True`;
- source-identity attestation fields;
- exact operation ID;
- contract family and API version;
- method/path;
- binding fingerprint;
- explicit non-production/runtime-denied posture.

`qualify_binding_from_discovery()` rejects assessments without a verified source pin, so another internal caller cannot bypass the Settings route by supplying an asserted `release_pinned=True` assessment.

External `$ref` handling is fail-closed at the Settings boundary: qualification requires a self-contained/bundled description. A caller-provided `external_references_resolved=True` flag cannot convert an external reference into evidence.

An existing provenance record without the stronger verified-source fields does not rehydrate as qualified and therefore requires requalification under the stronger boundary.

## Source identity attestation boundary

Immutable content and source identity are separate facts.

A matching artifact digest or structurally pinned git revision proves only that the submitted content is pinned. It does not prove which provider or standards body published it.

`endpoint_source_attestation.py` therefore uses an exact server-owned tuple:

`contract family + source reference + source kind + source revision + source SHA-256`

Only an exact match against a trusted server registry yields `source_identity_verified=True`. The default registry is deliberately empty, so arbitrary caller metadata cannot become provider identity. Any tuple drift, digest change, family change, or source-reference change fails closed to `source_identity_verified=False`.

Source identity attestation never grants `production_allowed` or `runtime_connector_approved`. Those remain separate qualification gates.

The current registry mechanism is intentionally a policy seam, not yet a trusted acquisition channel. A reviewed administrator/catalog acquisition path still has to populate trusted source records from an allowlisted provider repository or content-addressed artifact process.

## Binding mutation / drift protection

The provenance record carries a SHA-256 fingerprint over behavior-affecting, secret-free binding fields including base URL, method, path, task/adapter, credential-profile reference, scopes, request parameters, response mapping, status codes, and timeout.

A later binding mutation makes `provenance_matches_binding=False` and the runtime state becomes `drifted`; qualification cannot silently survive endpoint changes.

The raw OpenAPI/Swagger description is not stored in Settings provenance state.

## Qualification environment

`Sandbox Integration Qualification` provisions isolated PostgreSQL 17 and Redis 7, performs a clean `alembic upgrade head`, verifies sandbox authority migration `20260818_0055`, runs focused Ruff and qualification tests, and uploads evidence.

Run `#52` completed successfully and proved the focused commercial sandbox suite, including the clean migration chain, durable API-key lifecycle, durable quota/usage, PostgreSQL concurrency/no-overshoot, existing endpoint path/provenance contracts, and static Integration Center contracts.

Run `#61` completed successfully after the newer endpoint hardening and therefore provides focused CI evidence for Swagger media inheritance, undefined security-scheme rejection, server-derived source pinning, caller-boolean bypass prevention, bundled external-reference enforcement, and provenance drift/tamper contracts.

The subsequent server-owned source-identity attestation layer is implemented and wired into the qualification workflow, but its own post-change CI run is still pending at the time of this document update.

No production/provider credentials are present in this runner and `external_network_proof=false` remains explicit.

## CAMARA assessment

### Current posture

The runtime contract vocabulary recognizes `camara` as a contract family. This is architecture classification only. There is no registered executable CAMARA connector in the repository today.

`CAMARAArchitectureFamilyRecognized=True`

`CAMARAConnectorRegistered=False`

`CAMARAOpenAPIQualified=False`

`CAMARASandboxConnected=False`

`CAMARAProductionApproved=False`

### Semantic mapping requirement

CAMARA APIs are capability-specific. Identity/fraud prevention, location, device information, communication quality/QoS, payments/charging, and other network APIs do not automatically map to the existing Maestro `network_assurance` task family.

Each API requires an explicit review:

`CAMARA operation -> CAMARA scopes/security -> Maestro adapter contract -> Maestro task -> canonical inputs -> data classification -> entitlement -> quota`

If no current task accurately represents the operation, a dedicated reviewed adapter/task contract must be added instead of forcing the API into a nearby semantic category.

### Release and live sandbox qualification

CAMARA discovery must use a pinned API release aligned with a specific meta-release and matching Commonalities / Identity and Consent Management guidance. WIP definitions are not acceptable qualification sources.

The current source-pin mechanism proves submitted-content identity or structural git-revision provenance. The source-attestation seam can distinguish trusted server records from caller claims, but the repository does not yet acquire/attest a CAMARA repository commit or release tag through a trusted provider-controlled channel. Controlled provider-source acquisition remains required before `CAMARAOpenAPIQualified` can become true.

A CAMARA live proof additionally requires an operator or channel-partner sandbox implementation, managed sandbox credential reference, controlled non-production test data, and retained evidence. An OpenAPI document proves contract shape; it does not prove operator availability, credential approval, or production readiness.

## TM Forum and other platforms

TM Forum is represented as a runtime contract family and is used for Telecom Ticketing and Order Management reference contracts. Swagger 2.0 global media declarations are handled correctly, but real compatibility still requires a specific pinned provider/operator artifact and sandbox proof.

The same discovery/provenance process applies to proprietary, legacy, and generic Enterprise APIs. Provider version, immutable contract acquisition, change policy, authentication profile, sandbox endpoint, acceptance tests, and mapping evidence remain provider/customer inputs.

## Next implementation gates

1. `ENDPOINT-DISCOVERY-QUALITY-01`
   - obtain a green run for the server-owned source-identity attestation layer;
   - add controlled source acquisition so trusted registry records are produced from an allowlisted provider repository/artifact path rather than manually asserted metadata;
   - expose safe discovery/source-identity state in Integration Center without implying live provider connectivity.
2. `CAMARA-CONTRACT-QUALIFICATION-01`
   - select one concrete CAMARA API and pinned release;
   - acquire it through a trusted source path and bundle external references;
   - inventory operations/security/test assets;
   - create a dedicated semantic Maestro task/adapter contract where necessary.
3. `CAMARA-SANDBOX-PROVIDER-01`
   - identify an operator/channel-partner sandbox implementation;
   - register target and managed secret references;
   - run hardened live proof with non-production data;
   - retain evidence without raw credentials or raw provider payloads.
4. `SETTINGS-SANDBOX-QUALIFICATION-01`
   - the commercial subscription sandbox chain has green run `#52` evidence;
   - remaining umbrella Settings work is the separate admin evaluation-key authority and legacy no-match cutover policy.

## Gate state

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: endpoint extraction/path/provenance hardening is CI-proven through run `#61`; source identity is now explicitly separated from pinning and has fail-closed server-registry semantics, but that newest attestation change still needs CI proof. Trusted external-provider acquisition and real provider sandbox evidence also remain outstanding.