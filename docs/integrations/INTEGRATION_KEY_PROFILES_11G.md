# Integration Key Profiles 11G

Status: `draft_review`

11G adds a client-visible operational profile catalog for integration API keys.

It is catalog-only.

It does not:

- issue API keys
- display raw secrets
- approve production connectors
- call external customer systems
- add runtime connectors
- change the existing API key lifecycle

Profiles:

- external_partner_access
- service_integration_read_only
- service_integration_support_ticketing
- service_integration_billing_read
- telecom_operations_sandbox
- document_metadata_access
- enterprise_core_status_read

Safety rules:

- production_allowed remains false
- runtime_connector_approved remains false
- enterprise plan is required
- integration readiness is required
- supervisor review is required for write-capable sandbox profiles

Concept separation:

API Key means controlled access to Maestro API.

Operational Profile means the intended purpose of that key.

Integration Readiness means review of missing customer inputs and controls.

Runtime Connector means actual customer-system execution. It is not enabled here.

Production Approval is a separate future decision.

Next phases:

- 11H expose profiles safely
- 11I client console selector
- 11J carry selected profile into client requests
