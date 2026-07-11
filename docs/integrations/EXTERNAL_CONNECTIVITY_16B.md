# EXTERNAL-CONNECTIVITY-16B

## Governed connector target and secret references

EXTERNAL-CONNECTIVITY-16B adds immutable, default-deny Control Plane metadata only for the connector contracts introduced by 16A. It does not create executable customer connectors, network transports, HTTP clients, background workers, or production approval.

## Registry scope

The 16B registry is derived from the immutable 16A connector registry and currently declares:

- 22 target references: one sandbox and one production structural reference for each of the 11 connector contracts.
- 7 secret references: one unresolved customer-vault reference for each credential profile used by those connector contracts.
- 22 environment bindings: one disabled binding for every declared connector/environment pair.

Declaring a production-shaped reference does not approve production. It records only the metadata that an operator must later review.

## Target references

A `ConnectorTargetReference` identifies:

- the connector id;
- the declared environment;
- a normalized target alias;
- an endpoint reference name;
- configuration, validation, approval, runtime, HTTP, and production flags.

A target alias is not an endpoint. The registry contains no customer endpoint URL, hostname, IP address, path, query string, or transport configuration.

## Secret references

A `ConnectorSecretReference` identifies:

- the credential profile id;
- the reference kind `customer_vault_reference`;
- a normalized provider reference name;
- whether the reference is required and customer supplied;
- default-deny storage, visibility, resolution, runtime, and production flags.

A secret reference is not secret material. The registry contains no secret value, API key, OAuth client secret, password, access token, refresh token, private key, certificate private key, webhook signing secret, or connection string.

## Environment bindings

A `ConnectorEnvironmentBinding` links one connector/environment pair to one target reference and the secret references required by the connector authentication profiles.

Every binding remains:

```text
approval_status=pending_operator_input
validation_status=unvalidated
configured=false
validated=false
approved=false
runtime_enabled=false
external_http_enabled=false
production_allowed=false
automatic_activation_allowed=false
credentials_resolved=false
```

Every secret reference also preserves:

```text
value_stored=false
raw_secret_visible=false
credentials_resolved=false
runtime_enabled=false
production_allowed=false
```

## Required operator inputs

Before a future sandbox proof can be reviewed, the operator must provide separately governed metadata for:

- approved target alias;
- endpoint reference metadata;
- credential reference metadata;
- technical contact;
- security review record.

16B does not collect or resolve these inputs. It declares the required input names only.

## Validation

The registry validation contract checks:

- unique target, secret, and binding ids;
- complete coverage of all connector/environment pairs;
- complete coverage of all connector authentication profiles;
- correct target-to-binding connector and environment alignment;
- correct secret-reference alignment with connector authentication profiles;
- absence of enabled execution or approval flags.

## Explicit exclusions

EXTERNAL-CONNECTIVITY-16B adds no:

- real endpoint;
- customer URL;
- DNS name or IP address;
- secret value or credential material;
- secret manager client;
- credential resolver;
- external HTTP request;
- runtime dispatcher;
- worker or queue;
- automatic activation;
- sandbox connection proof;
- production connector approval.

A later phase may define governed operation planning or a disabled mock dispatcher, but it must not reinterpret these references as runtime authorization.
