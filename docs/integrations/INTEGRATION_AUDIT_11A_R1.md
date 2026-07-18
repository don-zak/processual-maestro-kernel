# INTEGRATION-AUDIT-11A-R1 — Existing Integration Primitives Audit

Status: `draft_audit`.
Production adapter approved: `false`.
New connector runtime approved: `false`.
External HTTP calls approved: `false`.
Real credentials approved: `false`.

This audit documents the integration primitives that already existed in Maestro
before expanding the new sector adapter umbrella. It prevents the integration
roadmap from creating a parallel model that ignores current API key, client
readiness, and Enterprise integration workflows.

## 1. Audit conclusion

Maestro is not empty in the integration area.

The existing codebase already contains integration access, provisioning, request,
readiness, and usage logging primitives. However, these primitives are not the same
as customer-sector production adapters.

The correct classification is:

- existing primitives: access, readiness, request workflow, usage logging, plans;
- new 11A umbrella: sector classification and adapter readiness language;
- missing layer: centralized scope catalog, adapter contracts, credential profiles,
  readiness checks, acceptance criteria, and customer-specific connector runtime.

## 2. Existing API key access primitives

Existing API key primitives include:

- `external_partner`;
- `service_integration`;
- Service Integration server-to-server access;
- Integration API key preset;
- API Key for integration;
- client identifiers such as `integration-client`;
- user identifiers such as `integration-user`;
- explicit service scopes;
- safe external usage logging;
- revocation behavior for generated keys.

These primitives should be reused by future integration readiness work. A future
sector adapter must not create a separate, incompatible key lifecycle.

## 3. Existing client integration readiness UI

Existing client-side integration readiness primitives include:

- `/settings/api-key-integration`;
- API Key Integration card;
- Enterprise-only client integration status;
- integration key count;
- integration scopes display;
- integration key list rendering;
- Client Integration Guide;
- copy-safe quickstart;
- placeholder auth header using `<client-integration-key>`;
- instruction not to paste raw provider secrets or raw integration keys.

This means the user-facing client readiness surface already exists. Future adapter
work should extend or align with it rather than replacing it.

## 4. Existing integration request workflow

Existing request workflow primitives include:

- `integration_key_provisioning`;
- `integration_key_rotation`;
- `integration_key_deactivation`;
- `enterprise_integration_upgrade`;
- safe support message preparation;
- no raw integration secret in support notes;
- supervisor or admin follow-up through Requests & Billing.

Future sector adapter work should keep these request types and should not introduce
a second integration-request vocabulary without migration.

## 5. Existing Enterprise integration plan layer

Existing plan and entitlement primitives include:

- `enterprise_integration_starter`;
- `enterprise_integration`;
- Enterprise Integration Starter;
- Enterprise Integration;
- `allows_enterprise_integration`;
- Enterprise-only gating for API key integration;
- non-enterprise plans are not allowed to use Enterprise integration.

Future sector adapter work should treat sector adapters as Enterprise or
integration-scoped capabilities, not as default self-service subscription behavior.

## 6. Existing usage logging and quota primitives

Existing logging and quota primitives include:

- `session_type="service_integration"`;
- `client_id="integration-client"`;
- `user_id="integration-user"`;
- safe external usage log entries;
- rejected scoped request logging;
- plan-aware usage metadata;
- integration key usage proof tests.

Future scope catalog work should preserve these usage and rejection logging patterns.

## 7. Existing platform-specific integrations

The codebase also contains platform-specific integrations such as:

- Discord webhook notification support;
- billing webhook support;
- Lemon Squeezy historical billing integration references.

These are platform integrations. They are not customer-sector adapters for telecom,
banking, government, research, university, or generic enterprise systems.

Future adapter work must keep this distinction clear.

## 8. Relationship to INTEGRATION-ADAPTERS-11A

The 11A sector adapter umbrella added declarative sector profiles for:

- Telecom;
- Banking;
- Government;
- Research Center;
- University;
- Generic Enterprise.

11A-R1 confirms that this umbrella does not replace the existing API key integration
workflow. Instead, it should sit above the existing access primitives.

The intended layering is:

1. Sector profile classifies the customer domain.
2. Scope catalog defines allowed, write, and restricted actions.
3. Existing API key lifecycle provisions governed access.
4. Client readiness UI shows integration status and key readiness.
5. Supervisor and admin workflows approve risky actions.
6. Adapter contracts define customer-system behavior.
7. Customer-specific connectors are added only after scoping and approval.

## 9. Missing layer confirmed by audit

The audit did not identify production-ready sector adapters such as:

- Telecom CRM adapter;
- Telecom Billing adapter;
- Telecom Ticketing adapter;
- Banking KYC adapter;
- Government Case adapter;
- University Student adapter;
- Research Dataset adapter;
- Generic Enterprise Helpdesk adapter.

The audit also confirms that these items still need future work:

- centralized integration scope catalog;
- adapter contract base model;
- credential profile model;
- sandbox and production environment model;
- integration readiness checks;
- acceptance criteria model;
- customer-specific connector runtime;
- admin integration readiness UI.

## 10. Guardrails for 11B

The next phase, `INTEGRATION-SCOPES-11B`, should be built on top of the existing
primitives and must follow these rules:

- reuse `external_partner` and `service_integration` concepts;
- preserve `/settings/api-key-integration`;
- preserve existing integration key request types;
- preserve safe support-message behavior;
- preserve Enterprise plan gating;
- preserve service integration usage logging;
- avoid real customer endpoints;
- avoid real credentials;
- avoid external HTTP calls;
- avoid production connector behavior;
- avoid writing a second incompatible key lifecycle.

## 11. Publication restrictions

This audit must not be used as:

- production adapter approval;
- proof that customer-sector connectors exist;
- customer API compatibility guarantee;
- credential approval;
- write-action approval;
- security approval;
- acceptance-test approval.

It is an internal alignment document for the next integration readiness phases.
