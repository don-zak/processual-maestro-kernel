# Integration Key Profiles 11J

Status: draft_review

11J carries the client-selected operational API key profile into integration key client requests.

Scope:

- client request message metadata only
- no new backend route
- no new API key lifecycle
- no API key issuing
- no raw secret display
- no runtime connector
- no production connector approval

Request metadata lines:

- integration_key_profile_id
- operational_profile_display_name
- base_key_profile
- operational_profile_environment
- requested_scopes
- forbidden_scopes
- requires_enterprise_plan
- requires_integration_readiness
- requires_supervisor_for_write
- production_allowed
- runtime_connector_approved
- operational_profile_next_action

Safety messages:

- Production connector approval remains separate.
- Runtime connectors are not approved from this request.
- No raw integration secret is included.

11J does not yet change Admin request detail rendering.

A later Admin phase may parse and highlight these metadata lines for supervisors.
