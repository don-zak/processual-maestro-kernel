# Integration Key Profiles 11H

Status: draft_review

11H safely exposes the client-visible operational API key profiles created in 11G.

The exposure is intentionally conservative.

Route strategy:

/settings/api-key-integration

11H augments the existing client API key integration payload.

It does not create a new key lifecycle.
It does not create a new API key.
It does not expose raw secrets.
It does not approve production connectors.
It does not enable runtime connectors.

Locked clients:

operational_profiles_enabled = false
operational_profiles = []
operational_profile_count = 0

Safety flags remain explicit:

raw_secret_visible = false
production_allowed = false
runtime_connector_approved = false
integration_readiness_required = true
supervisor_approval_required = true

Eligible clients:

When API Key Integration is available for the current client plan, the response includes the 11G client-visible profiles as metadata only.

These profiles describe intended Maestro API usage.

They do not authorize customer-specific production integrations.

Separation preserved:

API Key = controlled access to Maestro API
Operational Profile = declared purpose of API usage
Integration Readiness = review of blockers and security controls
Runtime Connector = real customer-system execution, not enabled here
Production Approval = separate future decision

Next phase:

11I should render these profiles in the client Settings API Key Integration card as a selector.

11I must remain UI-only and must not issue keys or approve connectors.
