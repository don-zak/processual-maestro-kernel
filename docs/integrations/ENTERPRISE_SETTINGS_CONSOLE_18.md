# Enterprise Settings Console 18

Status: `draft_review`

Production connector approved: `false`.
Real customer credentials approved: `false`.
Runtime connector approved: `false`.

## Purpose

The Enterprise Integration area in client Settings is a client-safe control and
readiness surface. It composes existing plan entitlement, API/service identity,
operational profile, scope-catalog, and declarative readiness primitives without
creating a second integration lifecycle.

The authoritative client contract is:

`GET /settings/enterprise-integration`

## Contract boundaries

The Settings console may expose:

- enterprise entitlement status;
- public and canonical plan identity plus legacy compatibility state;
- active client-safe integration key metadata;
- operational profile metadata already approved for client visibility;
- aggregate scope posture for read, write, restricted, pilot, and approval state;
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
profiles, scope posture details, and readiness details are not returned as
actionable Enterprise content.

### Available

Eligible Enterprise Integration plans receive the console lifecycle:

1. Enterprise entitlement.
2. API & service identity.
3. Profiles & scope posture.
4. Integration readiness.
5. Production approval.

Production approval remains `blocked` in the Settings contract.

## Plan authority

Eligibility is derived from the centralized
`enterprise_integration_capability()` contract in
`processual_api.billing.usage_pricing`.

The public plan identifier and canonical plan identifier are intentionally
separate concepts. Historical/public aliases such as `enterprise` and
`enterprise_integration` remain stable where compatibility requires them, while
`canonical_plan_id` resolves the fulfillment-catalog identity used by workflows
that require canonical plan application.

`enterprise_custom` remains Enterprise-eligible without implying a fixed catalog
quota. `enterprise_private` remains an explicit legacy compatibility plan while
that compatibility is required.

The client UI must not infer Enterprise eligibility from plan-name prefixes as
a security or entitlement boundary. Server responses remain authoritative.

## Scope posture authority

Scope posture is derived from the existing integration scope catalog. The
Settings contract exposes aggregate counts only; it does not invent a second
scope catalog or grant scopes. The payload explicitly marks this provenance as:

```text
scope_posture.source = catalog
```

That field is descriptive provenance, not a customer authorization decision.
The client UI labels the surface as `Catalog scope posture` and explicitly states
that the counts are not granted client permissions.

The aggregate posture covers:

- read scopes;
- write scopes;
- restricted scopes;
- read-only pilot eligibility;
- supervisor approval requirements;
- production-without-approval posture.

The following invariant remains mandatory:

```text
production_allowed_without_approval = 0
```

Write and restricted activity remains subject to the existing approval and
sandbox requirements declared by the scope catalog.

## Readiness authority

Readiness data comes from the existing declarative integration readiness
catalog. The Settings console does not itself approve a connector. Readiness
checks are evaluated once for each console response so the detailed checks and
aggregate summary represent the same evaluation snapshot.

A readiness check may indicate sandbox readiness, but all client-facing records
continue to enforce:

```text
production_allowed = false
runtime_connector_approved = false
```

## UI/UX requirements

The Settings Integration tab follows the existing Stage 18 layout system and
consumes `/settings/enterprise-integration` as the server-authoritative overview
source.

The Enterprise control-plane enhancement presents four information layers:

1. Enterprise identity, separating public and canonical catalog identity.
2. Catalog scope posture, with explicit provenance and least-privilege language.
3. Qualification readiness, including checks, sandbox-ready count, blockers, and
   the next safe action.
4. A persistent production boundary showing that production and runtime approval
   remain blocked.

The enhancement is read-only. It adds no production activation control and uses
safe text rendering for response-derived values. Failure to load the contract is
displayed as a fail-closed state rather than inferring entitlement or approval.

The surface must keep semantic tab/tabpanel relationships, keyboard navigation,
visible focus in the parent Settings system, responsive behavior, RTL-safe
logical layout, accessible live status, tabular numeric metrics, and
reduced-motion support. Raw secret material must never be rendered.

Existing detailed Integration cards may remain temporarily for compatibility,
but they must not override server-authoritative entitlement or production state.

## Tests

The stage is protected by tests covering:

- centralized Enterprise capability aliases and legacy compatibility;
- separation of public and canonical plan identities;
- `enterprise_custom` compatibility;
- locked-plan data minimization;
- client-key isolation;
- secret redaction;
- explicit catalog provenance;
- scope-count consistency;
- single-snapshot readiness evaluation;
- zero production scopes without approval;
- production/runtime fail-closed invariants;
- canonical Enterprise analytics roll-up without losing `client_requests` source;
- route registration;
- Settings tab ARIA relationships;
- keyboard navigation and roving tab index;
- responsive, RTL-safe, and reduced-motion control-plane layout behavior;
- safe text rendering and accessible live status;
- server-authoritative console loading without plan-prefix guessing.

## Next stage

The next controlled stage is customer-specific sandbox qualification: connect
approved customer configuration to the existing profile, scope, and readiness
contracts while keeping all runtime execution and production activation behind
supervised gates.

Customer-specific connector activation, real credentials, runtime connector
approval, and production canary remain later supervised qualification stages
and are not approved by this document.
