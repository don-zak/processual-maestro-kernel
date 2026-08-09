# Enterprise Settings Console 18

Status: `draft_review`

Production connector approved: `false`.
Real customer credentials approved: `false`.
Runtime connector approved: `false`.

## Purpose

The Enterprise Integration area in client Settings is a client-safe control and
readiness surface. It composes existing plan entitlement, API/service identity,
operational profile, and declarative readiness primitives without creating a
second integration lifecycle.

The authoritative client contract is:

`GET /settings/enterprise-integration`

## Contract boundaries

The Settings console may expose:

- enterprise entitlement status;
- normalized plan identity and legacy compatibility state;
- active client-safe integration key metadata;
- operational profile metadata already approved for client visibility;
- declarative integration readiness summaries and blocking reasons;
- sandbox environment posture;
- the next safe action.

The Settings console must never expose:

- raw API secrets after issuance;
- API-key hashes;
- encrypted provider credentials;
- customer connector credentials;
- OAuth secrets;
- mTLS private material;
- webhook secrets;
- cross-client integration key metadata;
- production approval as a client self-service action.

## Client states

### Locked

Non-eligible plans receive an upgrade-only contract. Key metadata, operational
profiles, and readiness details are not returned as actionable Enterprise
content.

### Available

Eligible Enterprise Integration plans receive the console sections:

1. Enterprise entitlement.
2. API & service identity.
3. Integration readiness.
4. Production approval.

Production approval remains `blocked` in the Settings contract.

## Plan authority

Eligibility is derived from the centralized
`enterprise_integration_capability()` contract in
`processual_api.billing.usage_pricing`.

Current authoritative Enterprise Integration plans remain the plan-fulfillment
catalog plans exposed through that capability contract. `enterprise_private`
is retained only as an explicit legacy compatibility plan while compatibility
remains required.

The client UI must not infer Enterprise eligibility from plan-name prefixes as
a security or entitlement boundary. Server responses remain authoritative.

## Readiness authority

Readiness data comes from the existing declarative integration readiness
catalog. The Settings console does not itself approve a connector.

A readiness check may indicate sandbox readiness, but all client-facing records
continue to enforce:

```text
production_allowed = false
runtime_connector_approved = false
```

## UI/UX requirements

The Settings Integration tab must follow the existing Stage 18 layout system.
It must keep semantic tab/tabpanel relationships, keyboard navigation, visible
focus, responsive behavior, and reduced-motion support.

The Enterprise console should present status, blockers, and the next safe action
before implementation details. Raw secret material must never be rendered.

## Tests

The stage is protected by tests covering:

- centralized Enterprise capability aliases and legacy compatibility;
- locked-plan data minimization;
- client-key isolation;
- secret redaction;
- production/runtime fail-closed invariants;
- route registration;
- Settings tab ARIA relationships;
- keyboard navigation and roving tab index;
- mobile and reduced-motion layout behavior.

## Next stage

After Public CI is green, extend the Settings UI to consume
`/settings/enterprise-integration` directly for the Enterprise overview and
next-action summary. Existing detailed cards may remain temporarily for
compatibility while the console becomes the authoritative presentation layer.

Customer-specific connector activation remains a later supervised qualification
stage and is not approved by this document.
