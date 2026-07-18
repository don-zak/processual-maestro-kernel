# EXTERNAL-CONNECTIVITY-16E-R2

## Customer-managed vault reference contract

`EXTERNAL-CONNECTIVITY-16E-R2` adds the first secret-manager abstraction
for the governed telecom ticketing sandbox pilot.

The selected mode is:

- customer-managed vault reference;
- reference-only;
- sandbox-only;
- unresolved;
- default-deny.

The contract status remains:

`pending_customer_vault_reference`

## Selected reference graph

The contract connects these existing references:

- pilot:
  `telecom_ticketing_read_only_sandbox_pilot`
- secret reference:
  `telecom_operations_api_reference_secret_reference`
- credential profile:
  `telecom_operations_api_reference`
- provider reference name:
  `telecom_operations_api_reference_pending_vault_reference`
- reference kind:
  `customer_vault_reference`

No referenced file is modified by this phase.

## Mandatory guardrails

The following statements are normative:

- no secret value
- no secret resolution
- no environment-variable lookup
- no network
- no credential logging
- no persistence
- no route
- no worker
- no runtime
- no production
- customer authorization required
- operator approval required
- security review required
- rotation policy required

The contract does not:

- accept a raw API key;
- accept an OAuth client secret;
- accept a password;
- accept an access token;
- accept a refresh token;
- accept a private key;
- accept a certificate private key;
- read an operating-system environment variable;
- call a cloud secret-manager SDK;
- call a customer vault;
- decrypt credential material;
- resolve credential material;
- return credential material;
- log credential material;
- persist credential material;
- create a worker;
- expose an application route;
- activate a connector;
- authorize production.

## Supported authentication references

The associated credential profile declares these reference methods:

- `api_key_reference`
- `oauth_client_reference`
- `mtls_certificate_reference`
- `customer_vault_reference`

These values identify possible reference forms only. They do not contain
authentication material.

## Forbidden material

The following material remains explicitly forbidden:

- raw API key values;
- raw OAuth client secrets;
- raw passwords;
- raw access tokens;
- raw refresh tokens;
- private key material;
- certificate private keys;
- webhook signing secret values;
- database connection strings.

## Required customer inputs

The existing credential profile requires:

- API documentation;
- sandbox access;
- test-credentials policy;
- scope matrix;
- technical contact;
- acceptance criteria;
- security requirements;
- credential owner;
- rotation policy;
- customer endpoint inventory.

R2 records the required input catalog but does not collect or persist the
real values.

## Required security controls

The contract preserves:

- enterprise review;
- security review;
- sandbox before production;
- least-privilege scopes;
- supervisor approval for production credentials;
- no raw secrets in support notes;
- customer vault or reference storage;
- required audit logging.

## Current readiness state

The current reference remains pending and unregistered:

- reference registered: false;
- reference validated: false;
- customer authorization present: false;
- operator approval present: false;
- security review completed: false;
- rotation policy confirmed: false;
- resolution allowed: false;
- credentials resolved: false;
- value stored: false;
- raw secret visible: false;
- runtime enabled: false;
- production allowed: false.

## Assessment behavior

`assess_connector_secret_manager_contract` validates only the immutable
reference graph.

Its current result is expected to report:

- contract valid: true;
- reference graph valid: true;
- provider reference pending: true;
- status: `pending_customer_vault_reference`;
- secret resolution disabled;
- runtime disabled;
- production disabled.

The assessment performs no secret lookup and grants no authority.

## Relationship to previous phases

R2 consumes but does not modify:

- connector runtime contracts;
- connector registry;
- target references;
- environment bindings;
- credential profiles;
- operation plans;
- mock dispatcher;
- sandbox pilot intake.

A later phase may define a no-network transport interface. Real secret
resolution and real sandbox connectivity require separate review and
customer-managed infrastructure.
