# ENDPOINT-DISCOVERY-AND-CAMARA-SANDBOX-R1

## Purpose

Establish a fail-closed qualification boundary for discovering external API
operations before creating Enterprise endpoint bindings, and define what is
actually required before CAMARA, TM Forum, proprietary, or generic Enterprise
platforms can be called from the Maestro sandbox.

## Current repository capability

The repository has a governed discovery/binding/execution chain:

1. `integration_task_catalog.py` defines provider-neutral Maestro tasks and
   canonical inputs.
2. `endpoint_discovery_quality.py` inventories a parsed OpenAPI/Swagger contract
   and blocks unsafe or incomplete discovery results.
3. `endpoint_binding_provenance.py` binds one exact discovered operation to a
   secret-free SHA-256 fingerprint of the endpoint binding and detects drift.
4. `enterprise_endpoint_bindings.py` binds an external operation to a canonical
   task, adapter contract, credential profile, scopes, request parameters,
   response mapping, allowed status codes, and timeout.
5. `enterprise_endpoint_request_mapping.py` maps canonical task inputs into JSON
   request bodies without allowing arbitrary canonical fields.
6. `enterprise_sandbox_execution.py` performs governed HTTPS execution with
   redirect blocking, DNS resolution, public-address enforcement, `trust_env`
   disabled, response-size limits, JSON-only response handling, transient
   credentials, mapping validation, task-injection evidence, and explicit
   non-production posture.
7. `settings_endpoint_discovery_qualification_runtime.py` re-runs discovery
   assessment server-side, stores only safe provenance metadata, and reports a
   previously qualified binding as `drifted` if its current fingerprint changes.
8. `sandbox_operational_readiness.py` requires binding, mapping, customer-scoped
   secret reference, non-production content contract, hardened live proof, and a
   provisioning fingerprint before reporting `sandbox_ready`.

This is a qualification foundation. It is not provider connectivity or
production authority.

## Endpoint discovery quality gate

Before this R1 slice, endpoint values were expected to be entered or known
manually. `endpoint_discovery_quality.py` now accepts an already parsed API
description and inventories:

- API dialect (`OpenAPI 3.0`, `OpenAPI 3.1`, or `Swagger 2.0`);
- title and API version;
- operation IDs and duplicates;
- HTTP method and path;
- path parameter declarations and required posture;
- OAuth/security scopes visible in the API description;
- request and response media types;
- response status contracts;
- external `$ref` dependencies;
- server/base-path hints;
- canonical SHA-256 of the supplied contract;
- source provenance supplied to the qualification request.

Binding generation is blocked for moving/unpinned input, missing or duplicate
operation IDs, invalid path-parameter contracts, unresolved external references,
or missing response contracts. CAMARA adds OpenAPI 3, non-WIP version,
`x-camara-commonalities`, and versioned-server requirements.

## Path composition hardening: implemented

`enterprise_endpoint_bindings.build_request_preview()` now percent-encodes each
task-derived path value as one path segment and rejects unresolved placeholders.
Regression tests cover `/`, `?`, `#`, dot-segment input, already encoded
separators, Unicode values, and ordinary identifiers.

This prevents canonical task values from changing the route shape after a
binding has been validated.

## Discovery provenance binding: implemented, CI proof pending

`endpoint_binding_provenance.py` creates a non-production provenance record only
when:

- discovery quality passed;
- binding generation is ready;
- one `operationId` matches exactly once;
- discovered method and path match the binding exactly;
- source reference, source SHA-256, contract family, and API version are present;
- discovery itself does not grant production or runtime authority.

The record also carries a SHA-256 fingerprint over behavior-affecting,
secret-free binding fields including base URL, method, path, task/adapter,
credential profile reference, scopes, request parameters, response mapping,
status codes, and timeout.

`settings_endpoint_discovery_qualification_runtime.py` recomputes the discovery
assessment server-side from the supplied API description. It does not persist
the raw API description. It stores only safe provenance metadata. A later
binding mutation makes `provenance_matches_binding=False` and the runtime state
becomes `drifted`; an old record therefore cannot silently retain active
qualification after endpoint changes.

This still does not prove that the named source reference is externally
reachable or that a provider/operator deployed the contract. The content digest
binds the exact submitted document; external release/provider verification
remains a separate qualification step.

## Sandbox qualification environment

`Sandbox Integration Qualification` now provisions isolated PostgreSQL 17 and
Redis 7, performs a clean `alembic upgrade head`, verifies the sandbox authority
migration, runs focused Ruff and qualification tests, and uploads evidence.
Changes anywhere under `alembic/versions/**` retrigger the clean-chain test.

The first PostgreSQL run exposed an older migration defect in
`20260807_0039_top_up_quota_grants.py`: direct equality against a PostgreSQL
`json` column was not portable. The migration now casts inserted entitlement
payloads to JSON and compares empty/null JSON through a text projection. A
regression contract prevents the unsafe comparison from returning.

A subsequent run proved the clean Alembic chain through `20260818_0055` and
passed Ruff. Its focused pytest slice reached 60 passing tests and one test
fixture assertion mismatch; that assertion was corrected to exercise the
intended SHA-256 validator. The latest qualification run remains the source of
truth for final pass/fail status.

No production/provider credentials are present in this runner and
`external_network_proof=false` remains explicit.

## CAMARA assessment

### Current posture

The runtime contract vocabulary recognizes `camara` as a contract family. This
is architecture classification only. There is no registered executable CAMARA
connector in the repository today.

The correct current state remains:

`CAMARAArchitectureFamilyRecognized=True`

`CAMARAConnectorRegistered=False`

`CAMARAOpenAPIQualified=False`

`CAMARASandboxConnected=False`

`CAMARAProductionApproved=False`

### Semantic mapping requirement

CAMARA APIs are capability-specific. Identity/fraud prevention, location,
device information, communication quality/QoS, payments/charging, and other
network APIs do not automatically map to the existing Maestro
`network_assurance` task family.

Each API requires an explicit review:

`CAMARA operation -> CAMARA scopes/security -> Maestro adapter contract ->
Maestro task -> canonical inputs -> data classification -> entitlement -> quota`

If no current task accurately represents the operation, a dedicated reviewed
adapter/task contract must be added instead of forcing the API into a nearby
semantic category.

### Release and live sandbox qualification

CAMARA discovery must use a pinned API release aligned with a specific
meta-release and matching Commonalities / Identity and Consent Management
guidance. WIP definitions are not acceptable qualification sources.

A CAMARA live proof additionally requires an operator or channel-partner sandbox
implementation, managed sandbox credential reference, controlled non-production
test data, and retained evidence. An OpenAPI document proves a contract shape;
it does not prove operator availability, credential approval, or production
readiness.

## TM Forum and other platforms

TM Forum is represented as a runtime contract family and is used for Telecom
Ticketing and Order Management reference contracts. This remains
architecture/contract-level compatibility until a specific provider API version
and real sandbox binding are qualified.

The same discovery/provenance process applies to proprietary, legacy, and
generic Enterprise APIs. Provider version, immutable contract input, change
policy, authentication profile, sandbox endpoint, acceptance tests, and mapping
evidence remain provider/customer inputs.

## Next implementation gates

1. `ENDPOINT-DISCOVERY-QUALITY-01`
   - obtain a green qualification run for path composition, provenance, runtime
     drift, migration, API-key, and UI contracts;
   - expose the safe discovery state in Integration Center without implying live
     provider connectivity.
2. `CAMARA-CONTRACT-QUALIFICATION-01`
   - select one concrete CAMARA API and pinned release;
   - bundle/resolve external references;
   - inventory operations/security/test assets;
   - create a dedicated semantic Maestro task/adapter contract where necessary.
3. `CAMARA-SANDBOX-PROVIDER-01`
   - identify an operator/channel-partner sandbox implementation;
   - register target and managed secret references;
   - run hardened live proof with non-production data;
   - retain evidence without raw credentials or raw provider payloads.
4. `SETTINGS-SANDBOX-QUALIFICATION-01`
   - wire durable API-key authentication with fail-closed durable-match
     semantics;
   - migrate issuance/rotation/revocation authority to PostgreSQL;
   - connect metered requests to existing durable subscription usage authority;
   - execute concurrency/no-overshoot proof.

## Gate state

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: path composition and server-side provenance/drift controls are now
implemented, and the clean PostgreSQL migration chain has been demonstrated in
CI. A fully green latest qualification run, pinned external provider releases,
real provider sandboxes, durable API-key wiring, quota concurrency evidence, and
rendered browser qualification are still required before any higher gate can be
raised.
