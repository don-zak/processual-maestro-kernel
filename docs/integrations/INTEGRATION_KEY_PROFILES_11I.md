# Integration Key Profiles 11I

Status: draft_review

11I renders the 11G/11H operational API key profiles inside the client Settings API Key Integration card.

Scope:

- UI selector only
- no new backend route
- no API key issuing
- no raw secret display
- no runtime connector
- no production connector approval
- no structured client request propagation yet

Displayed client-safe metadata:

- profile id
- display name
- base key profile
- sandbox environment
- allowed scopes
- forbidden scopes
- enterprise plan requirement
- integration readiness requirement
- supervisor review requirement
- production_allowed=false
- runtime_connector_approved=false

11I keeps the selected profile in the browser UI only.

11J will carry the selected operational profile into client requests as structured metadata.

Safety message: Production connector approval remains separate. Runtime connectors are not approved from this selector. Raw integration secrets are never displayed.
