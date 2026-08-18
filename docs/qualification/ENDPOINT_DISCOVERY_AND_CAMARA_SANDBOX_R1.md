# ENDPOINT-DISCOVERY-AND-CAMARA-SANDBOX-R1

## Purpose

Establish a fail-closed qualification boundary for discovering external API
operations before creating Enterprise endpoint bindings, and define what is
actually required before CAMARA, TM Forum, proprietary, or generic Enterprise
platforms can be called from the Maestro sandbox.

## Current repository capability

The repository already has a strong governed binding/execution chain:

1. `integration_task_catalog.py` defines provider-neutral Maestro tasks and
   canonical inputs.
2. `enterprise_endpoint_bindings.py` binds an approved external operation to a
   canonical task, adapter contract, credential profile, scopes, request
   parameters, response mapping, allowed status codes, and timeout.
3. `enterprise_endpoint_request_mapping.py` maps canonical task inputs into JSON
   request bodies without allowing arbitrary canonical fields.
4. `enterprise_sandbox_execution.py` performs governed HTTPS execution with
   redirect blocking, DNS resolution, public-address enforcement, `trust_env`
   disabled, response-size limits, JSON-only response handling, transient
   credentials, mapping validation, task-injection evidence, and explicit
   non-production posture.
5. `sandbox_operational_readiness.py` requires binding, mapping, customer-scoped
   secret reference, non-production content contract, hardened live proof, and a
   provisioning fingerprint before reporting `sandbox_ready`.

This is a useful execution foundation. It is not, by itself, an endpoint
*discovery* authority.

## Finding: endpoint discovery was previously manual

Before this R1 slice, the binding contract expected `base_url`, `method`,
`path`, scopes, field mapping, and status codes to already be known. The
repository did not contain a dedicated OpenAPI/Swagger discovery quality gate
that could prove these values were extracted from a pinned external contract.

`processual_api/integrations/endpoint_discovery_quality.py` now fills that
read-only boundary. It does not fetch a URL and does not execute a request. It
accepts an already parsed and review-pinned API description and inventories:

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
- SHA-256 of the supplied contract;
- immutable source provenance supplied by the qualification runner.

Binding generation remains blocked when a required quality condition fails.

## Endpoint extraction quality gates

An extracted endpoint is not considered binding-ready merely because a parser
can find a path. Qualification requires all of the following:

- source points to a reviewed immutable release/tag/artifact, not a moving
  branch;
- supported OpenAPI/Swagger dialect;
- title and semantic API version are present;
- every operation used for binding has a unique `operationId`;
- every `{pathParameter}` has a declared and required path parameter contract;
- external schema references are resolved/bundled before qualification;
- response contracts are declared;
- request media type is reviewed for body methods;
- security scopes are extracted and compared to Maestro scopes rather than
  copied into authority automatically;
- endpoint method/path is still validated against the canonical Maestro task;
- no discovered operation grants production authority automatically.

## Additional path-composition blocker

`enterprise_endpoint_bindings.build_request_preview()` currently substitutes
canonical task values into path placeholders as strings. Before the discovery
pipeline can be declared fully qualified, path values must be percent-encoded
as path-segment data and tests must prove that `/`, `?`, `#`, `..`, and encoded
separator input cannot change the intended endpoint route.

This is a binding-quality blocker even though the network execution layer
already blocks redirects and non-public destinations.

## Sandbox execution environment inventory

### Available in repository

- Python 3.14 project configuration.
- FastAPI/httpx execution stack.
- SQLAlchemy/asyncpg/Alembic database dependencies.
- Redis client dependency.
- A Redis-backed `Durable Preproduction Qualification` workflow that can be
  manually dispatched and uploads qualification evidence.
- Enterprise sandbox credential resolver using deployment environment references
  (`MAESTRO_SANDBOX_AUTHORIZATION_<PROFILE>` or
  `MAESTRO_SANDBOX_API_KEY_<PROFILE>`).
- sandbox secret-reference/content/readiness contracts.
- external HTTP sandbox executor with DNS/public-IP checks and evidence hashes.

### Missing for this exact qualification

The existing durable preproduction workflow starts Redis but does not start a
PostgreSQL service and does not exercise endpoint discovery, durable sandbox API
keys, or external connector live proof. Therefore it cannot currently prove the
full Settings Sandbox chain.

A dedicated qualification runner is still required with:

- isolated PostgreSQL at the declared Alembic head;
- isolated Redis;
- no production credentials;
- pinned provider OpenAPI artifacts;
- provider/operator sandbox credentials supplied as managed secrets/references;
- controlled outbound HTTPS and DNS;
- test fixtures or synthetic customer content;
- concurrency tests for quota authority;
- endpoint discovery/binding/mapping tests;
- deterministic cleanup;
- evidence artifact upload.

## CAMARA assessment

### What the repository currently supports

The generic runtime contract vocabulary recognizes `camara` as a contract
family. This is only an architecture classification.

There is currently no registered executable CAMARA connector in the repository.
The Telecom reference connectors are CRM, Billing, Ticketing, Order Management,
and Network Assurance references, and their current contract families are
proprietary, legacy, or TM Forum. Their external API versions remain
`pending_operator_input`.

Therefore the correct current statement is:

`CAMARAArchitectureFamilyRecognized=True`

`CAMARAConnectorRegistered=False`

`CAMARAOpenAPIQualified=False`

`CAMARASandboxConnected=False`

`CAMARAProductionApproved=False`

### Why CAMARA must not be mapped blindly to Network Assurance

CAMARA APIs are capability-specific. Examples include identity/fraud prevention,
location, device information, communication quality/QoS, payments/charging, and
other network APIs. Their subject identifiers, consent/security profiles,
request bodies, and operational semantics are not equivalent to the existing
Maestro `network_assurance` task family.

A CAMARA API must therefore receive an explicit semantic mapping review:

`CAMARA operation -> CAMARA scopes/security -> Maestro adapter contract ->
Maestro task -> canonical inputs -> data classification -> entitlement -> quota`

If no current Maestro task accurately represents the CAMARA operation, the
correct action is to add a reviewed adapter/task contract, not to force the API
into the nearest existing task.

### CAMARA release qualification

CAMARA endpoint discovery must use a pinned API release that is aligned with a
specific CAMARA meta-release and matching Commonalities / Identity and Consent
Management guidance. WIP API definitions are not acceptable qualification
sources. The discovery gate also requires the CAMARA
`x-camara-commonalities` declaration and a versioned server contract before
binding generation can be considered ready.

A CAMARA live proof additionally requires an operator or channel-partner sandbox
implementation. A CAMARA OpenAPI document alone proves an API contract, not that
an operator endpoint or credential has been approved.

## TM Forum and other platforms

The repository already contains TM Forum as a runtime contract family and uses
it for the Telecom Ticketing and Order Management reference contracts. This is
still architecture-level compatibility until a specific operator/provider API
version is reviewed and a real endpoint binding is qualified.

The same discovery process applies to proprietary, legacy, and generic
Enterprise APIs. The difference is that provider-specific qualification may not
have a cross-industry meta-release. In those cases the immutable contract source,
provider version, change policy, authentication profile, sandbox endpoint,
acceptance tests, and mapping evidence become mandatory customer/provider input.

## Next implementation gates

1. `ENDPOINT-DISCOVERY-QUALITY-01`
   - run focused tests for the new discovery module;
   - add path-segment encoding/route-injection protection;
   - bind discovery output to binding creation with a source SHA/provenance check.
2. `CAMARA-CONTRACT-QUALIFICATION-01`
   - select one concrete CAMARA API and pinned release;
   - bundle/resolve external references;
   - inventory operations/security/test assets;
   - decide whether an existing Maestro adapter/task is semantically valid;
   - otherwise create a dedicated reviewed task contract.
3. `CAMARA-SANDBOX-PROVIDER-01`
   - identify an operator/channel partner sandbox implementation;
   - register target and managed secret references;
   - run hardened live proof with non-production data;
   - retain evidence without raw credentials or raw provider payloads.
4. `SETTINGS-SANDBOX-QUALIFICATION-01`
   - continue durable API-key wiring and PostgreSQL/Redis quota qualification;
   - only then bind external-client authority to the qualified endpoint pipeline.

## Gate state

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: discovery quality tooling now exists in code, but path-composition
hardening, focused CI execution, pinned provider specifications, real provider
sandboxes, durable API-key wiring, and PostgreSQL/Redis end-to-end evidence are
still outstanding.
