# TRUSTED-SOURCE-BUNDLE-R1

## Purpose

Record the fail-closed qualification boundary for resolving relative OpenAPI/Swagger `$ref` resources acquired from a server-owned immutable GitHub source definition.

This stage does **not** establish provider sandbox connectivity, runtime connector approval, production authority, or live-source qualification.

## Qualified contract

`trusted_endpoint_source_acquisition.py` now separates the root API-description allowlist from the reference-resource allowlist:

- `allowed_path_prefixes` constrains caller-selectable root descriptions;
- `allowed_reference_prefixes` independently constrains repository-relative resources referenced by `$ref`;
- root and reference files must use the same server-owned GitHub repository and the exact same allowlisted immutable commit;
- the fetch host remains fixed to `raw.githubusercontent.com`;
- redirects and proxy-environment inheritance remain disabled;
- public-address DNS resolution is required before acquisition.

The reviewed CAMARA Quality on Demand r3.2 candidate remains pinned to:

- source identity: `camara.quality_on_demand.r3_2`;
- repository: `camaraproject/QualityOnDemand`;
- commit: `9cb179fd3b63f43d564c76689295cd681e723548`;
- root path: `code/API_definitions/quality-on-demand.yaml`;
- allowed root prefix: `code/API_definitions`;
- allowed reference prefix: `code/common`;
- policy: `camara-public-release-review-r1`.

The candidate is **not** automatically inserted into the runtime trusted-source catalog. An empty server configuration still yields an empty trusted-source catalog.

## Relative-reference policy

The resolver inspects `$ref` only. It does not follow `externalDocs`, images, prose URLs, or arbitrary links.

Accepted reference forms:

- fragment-only references such as `#/components/schemas/Example`, which require no network fetch;
- repository-relative JSON/YAML references plus an optional fragment.

Rejected before reference network access:

- absolute or scheme-bearing URLs;
- protocol-relative URLs;
- backslash paths;
- query-bearing references;
- percent-encoded path tricks;
- paths escaping the repository root;
- normalized paths outside `allowed_reference_prefixes`.

Relative paths are normalized against the parent repository path. A legitimate CAMARA-style reference such as `../common/CAMARA_common.yaml#/...` resolves to `code/common/CAMARA_common.yaml` and remains constrained to the same repository and commit.

## Resource bounds

The acquisition path is bounded by:

- 2 MiB maximum per fetched file;
- 8 MiB maximum aggregate bundle bytes;
- 16 maximum files per bundle;
- maximum reference depth of 8;
- cycle and duplicate-fetch suppression by normalized repository path.

The bundle produces deterministic safe provenance:

- the root document retains its canonical `source_sha256` for existing exact source attestation;
- `source_bundle_sha256` is computed from a sorted manifest of `(repository path, canonical document SHA-256)` tuples;
- `source_bundle_paths` contains only normalized repository paths, not raw documents or credentials.

## Settings qualification wiring

The trusted-source qualification route passes `external_references_resolved=True` only when acquisition proves that all discovered relative references were fetched and accepted within the trusted bundle policy.

Caller-supplied boolean claims still cannot grant this authority. The legacy caller-upload route remains fail-closed for external references.

The route may return safe bundle metadata (`trusted_source_bundle_sha256`, `trusted_source_bundle_paths`) while persisted Settings provenance remains secret-free and does not store the raw API description or bundle documents.

No bundle result can set `production_allowed=True` or `runtime_connector_approved=True`.

## Focused CI evidence

Run `#134` (`32211779079`) on head `f1e467151a4ea7c4cc6a985248bb35298e70c2a1` passed:

- PostgreSQL 17 / Redis 7 service checks;
- clean Alembic upgrade through `20260818_0056`;
- focused Ruff qualification slice;
- all focused qualification tests, including trusted relative-reference bundle and route tests;
- evidence recording and artifact upload.

Evidence artifact:

- artifact ID: `9351000001`;
- digest: `sha256:fe054b4ed995cb0d66d8076422ad6ee2318385963b5d1713ca244a0b57369e5a`.

The workflow evidence explicitly retains:

- `trusted_source_live_fetch=false`;
- `production_credentials=false`;
- `external_provider_credentials=false`;
- `external_network_proof=false`.

## Gate state

`SettingsSandboxQualified=False`

`SandboxApiKeysQualified=False`

`EndpointDiscoveryQualityQualified=False`

`CAMARAConnectorQualified=False`

`ExternalApiIntegrationQualified=False`

Reason: trusted relative-reference acquisition is now contract- and CI-proven, but the qualification runner has not live-fetched the reviewed public CAMARA release, no executable provider/operator sandbox connector is qualified, no provider credentials/network proof exist, and rendered browser/external-client E2E qualification remains outstanding.
