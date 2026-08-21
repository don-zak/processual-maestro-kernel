# CAMARA QoD Sandbox Transition Report — 2026-08-19

## 1. Purpose

This report is the transition record for the CAMARA Quality on Demand qualification work on PR #163 (`agent/settings-sandbox-qualification-r1`). It consolidates what is proven, what remains intentionally blocked, the evidence retained in the repository, the exact sandbox interoperability achieved with Telefonica Open Gateway, and the remaining review/qualification sequence before any connector, staging, or production authority can be considered.

The report is intentionally fail-closed. It does not convert mock/sandbox interoperability into operator-network proof, does not alter the approved CAMARA v1.1.0 governance contract, and does not authorize merge, staging, runtime connector execution, or production.

## 2. Current PR / authority state

At the verification point immediately before this report was created:

- PR: `#163` — `test: establish settings sandbox qualification baseline`
- base branch: `agent/admin-governance-foundation`
- head branch: `agent/settings-sandbox-qualification-r1`
- verified head before report commit: `9347146286901da23e11f95d03647811f2954734`
- PR state: open
- draft: true
- merged: false
- mergeable: true
- no Ready-for-review transition was requested or performed
- no merge/rebase/force-push/auto-merge action was requested or performed

Authority remains:

```text
runtime_connector_approved=false
provider_sandbox_proven=false            # for the governed CAMARA v1.1.0 contract
operator_network_qos_proven=false
production_allowed=false
staging_allowed=false
```

## 3. CI state

For head `9347146286901da23e11f95d03647811f2954734`:

- `CAMARA Public Source Contracts` — run `32238525090` — completed / success
- `Sandbox Integration Qualification` — run `32238525092` — completed / success

These runs prove repository contracts/tests for that exact head. They do not prove external operator network behavior.

## 4. Governed CAMARA contract

The approved contract remains immutable and pinned to:

- source identity: `camara.quality_on_demand.r3_2`
- API version: `1.1.0`
- source revision: `9cb179fd3b63f43d564c76689295cd681e723548`
- source path: `code/API_definitions/quality-on-demand.yaml`
- approved semantic blob: `70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- governance version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- governance decision: `approved_with_conditions`

Approved outbound operations:

1. `createSession` → `camara.qod.session_create`
2. `getSession` → `camara.qod.session_get`
3. `deleteSession` → `camara.qod.session_delete`
4. `extendQosSessionDuration` → `camara.qod.session_extend`
5. `retrieveSessionsByDevice` → `camara.qod.sessions_retrieve_by_device`

`postNotification` remains excluded from Maestro outbound binding because it is a provider-to-consumer callback.

## 5. Completed qualification layers

### 5.1 Public-source qualification

The exact pinned CAMARA public source was acquired and semantically qualified from isolated execution commit `f1595583ee573942d7ae131ec3572a863805c25e`.

Proven:

```text
source_identity_verified=true
external_references_resolved=true
discovery_quality_passed=true
semantic_mapping_aligned=true
public_source_qualification_ready=true
```

Retained digests:

- source SHA-256: `e67849832ac08f14634174c26f0f3634e8fcfe16922d6cd3bd0ccb394d410ff9`
- bundle SHA-256: `adc0d4c1c1ef85d63deebbefd3807a447d4560baef2e5458da4a2ea1e0a66c60`

This is standards-source proof only.

### 5.2 Governance approval

CAMARA-CLOSE-1 is complete with conditions.

The five tasks, two entitlement IDs, and five quota meters are approved for the exact reviewed semantic blob only. Governance approval does not grant provider credentials, endpoint execution, connector authority, staging, or production.

### 5.3 Runtime registration

CAMARA-CLOSE-2 is implemented.

The exact five tasks are registered in the dedicated CAMARA QoD runtime registry. Admission remains default-deny and requires:

- exact task entitlement;
- positive quota evidence;
- explicit write approval for create/delete/extend;
- governed provider sandbox proof;
- runtime connector approval.

Unknown tasks fail closed. `production_allowed` remains false even when a sandbox admission example satisfies lower-level gates.

### 5.4 Operator intake / offline preparation

Reference-only operator intake exists and rejects raw endpoints, tokens, secrets, certificates, keys, and payloads.

Offline request-plan precheck was executed successfully by the user and retained as:

`docs/qualification/evidence/CAMARA_QOD_OFFLINE_PRECHECK_2026-08-19.json`

It proves only local contract/preflight correctness. DNS, TLS, credentials, provider network, runtime connector, and production remained false.

## 6. Telefonica Open Gateway sandbox qualification

### 6.1 Sandbox application and authentication

A Telefonica Open Gateway Sandbox application was created for the QoD Mobile / Request Service Provisioning surface.

The application registration completed successfully. Client credentials were used only through local environment variables; no client secret was committed to the repository.

CIBA was exercised successfully:

```text
POST /bc-authorize -> 200
POST /token        -> 200
access token       -> obtained in memory only, expires_in=3600
```

This proves authenticated sandbox reachability for the Telefonica sandbox application.

### 6.2 Correct QoD route discovery

Initial requests to an obsolete/documentation-variant path containing `/ogw` returned generic gateway `404 Not Found`.

The Telefonica interactive API reference exposed the working route family:

```text
https://sandbox.opengateway.telefonica.com/apigateway/qod/v0
```

The successful executions therefore use `/apigateway/qod/v0`, not `/apigateway/ogw/qod/v0`.

### 6.3 Proven external QoD lifecycle

The user executed the CIBA-authenticated session lifecycle successfully:

```text
POST   /qod/v0/sessions                         -> 201
GET    /qod/v0/sessions/{sessionId}             -> 200
DELETE /qod/v0/sessions/{sessionId}             -> 204
```

The user then executed the extend lifecycle successfully:

```text
POST   /bc-authorize                            -> 200
POST   /token                                   -> 200
POST   /qod/v0/sessions                         -> 201
POST   /qod/v0/sessions/{sessionId}/extend      -> 200
GET    /qod/v0/sessions/{sessionId}             -> 200
DELETE /qod/v0/sessions/{sessionId}             -> 204
```

Retained public evidence:

`docs/qualification/evidence/TELEFONICA_QOD_CIBA_SESSION_LIFECYCLE_2026-08-19.json`

The retained record contains no client secret, access token, auth request ID, or session ID.

### 6.4 External qualification projection

The repository now explicitly models this proof separately from the governed provider gate:

- `processual_api/integrations/camara_qod_external_sandbox_qualification.py`
- `processual_api/integrations/camara_qod_telefonica_compatibility.py`
- `tests/test_camara_qod_telefonica_external_qualification.py`
- `docs/qualification/CAMARA_QOD_TELEFONICA_V0_10_COMPATIBILITY.md`

Current truthful state:

```text
authenticated_sandbox_reachability_proven=true
external_mock_sandbox_proven=true
external_mock_extend_proven=true
provider-proven operations:
  - createSession
  - getSession
  - deleteSession
  - extendQosSessionDuration
```

Still false:

```text
operator_network_qos_proven=false
governed_camara_v1_1_provider_sandbox_proven=false
provider_sandbox_proven=false
runtime_connector_approved=false
production_allowed=false
```

## 7. Compatibility boundary: Telefonica v0.10 vs governed CAMARA v1.1.0

| Operation | Governed CAMARA v1.1.0 | Telefonica v0.10 exercised shape | External proof | Qualification consequence |
| --- | --- | --- | --- | --- |
| `createSession` | `POST /sessions` | same | proven | partial semantic interoperability |
| `getSession` | `GET /sessions/{sessionId}` | same | proven | partial semantic interoperability |
| `deleteSession` | `DELETE /sessions/{sessionId}` | same | proven | partial semantic interoperability |
| `extendQosSessionDuration` | `POST /sessions/{sessionId}/extend` | same | proven | partial semantic interoperability |
| `retrieveSessionsByDevice` | `POST /retrieve-sessions` | not present in the exercised Telefonica v0.10 session surface | not proven | exact governed contract remains incomplete |

The provider API version is `v0.10`, while the governed contract is `v1.1.0`. Matching methods/paths for four operations are useful interoperability evidence but cannot be represented as exact-version provider proof.

Current public Telefonica QoD v0.10 documentation enumerates profile/session operations (create, get, extend, delete) but no `retrieveSessionsByDevice` operation was found in the exercised v0.10 surface. This must be treated as an unresolved compatibility gap, not silently waived.

## 8. Remaining work inside the sandbox phase

### S1 — exact external evidence completeness

Status: **partially complete**.

Completed:

- authenticated CIBA reachability;
- token exchange;
- create/get/delete lifecycle;
- extend lifecycle;
- sanitized retained evidence;
- compatibility projection with fail-closed boundaries.

Remaining:

- determine whether Telefonica exposes an equivalent of `retrieveSessionsByDevice` under another supported/current QoD API version or product surface;
- if no equivalent exists, record an explicit incompatibility decision; do not infer a waiver;
- verify failure behavior intentionally (at minimum: invalid input, unauthorized/expired token, missing session, conflict/idempotency behavior where safe);
- retain sanitized failure evidence without raw credentials or response bodies containing identifiers;
- confirm the exact provider API/version identifier from the interactive/API reference and pin it in compatibility evidence.

Exit criteria for S1:

- every governed operation is either externally proven on an exact compatible provider surface or explicitly classified as incompatible/unavailable with a governance decision;
- positive and negative-path evidence retained;
- no secret leakage.

### S2 — operator-network proof vs mock proof

Status: **not complete**.

Current success is sandbox/mock interoperability. To prove operator-network QoS behavior, obtain a non-mock/operator-backed test environment where the provider confirms network-backed execution.

Required evidence:

- operator/environment identity;
- endpoint and API version;
- managed credential reference;
- device/test-subject eligibility;
- QoS profile available in that operator environment;
- create request accepted;
- observable QoS/session state from provider;
- extend/get/delete behavior;
- provider/network failure semantics;
- evidence that the result is not a deterministic mock response.

Until then:

```text
operator_network_qos_proven=false
provider_sandbox_proven=false   # governed contract
```

### S3 — browser/client E2E and rendered admin validation

Status: **not complete**.

Required:

- Integration Center rendered state matches server truth;
- governance displays Approved, not Review required;
- runtime tasks display Registered/default-deny, not disabled;
- Telefonica external mock evidence is presented as separate non-authoritative evidence;
- provider/operator proof remains blocked;
- responsive layout validation;
- accessibility/keyboard/focus validation;
- browser/client E2E against safe admin endpoints;
- screenshots or deterministic UI evidence where appropriate.

Known remaining UI gap at report creation: `processual_api/static/js/admin_integration_center_18.js` still contains legacy logic expecting `governance_approved === false`, labels governance as `Review required`, and describes runtime task registration as disabled. This must be corrected before sandbox UI closure.

### S4 — secret-management and operational hygiene

Status: **partially complete**.

Completed:

- probes consume credentials from environment variables;
- evidence does not retain access token/client secret/auth_req_id/session ID;
- no production credentials used.

Remaining before any reusable connector:

- move provider credentials behind the project secret-manager reference model;
- prove secret lookup/rotation/revocation behavior;
- prevent secrets from command history/logging/process diagnostics where practical;
- define token refresh/expiry behavior;
- define environment separation for mock/operator/staging;
- define incident response/revocation procedure.

### S5 — sandbox connector candidate

Status: **not approved / not executable**.

A provider-specific compatibility adapter may only be proposed after S1/S2 decisions. It must be separate from the immutable governed semantic mapping.

Required before `runtime_connector_approved=true` can even be considered:

- exact provider contract/version pinned;
- operation mapping approved;
- auth flow contract approved;
- endpoint reference managed;
- secret references managed;
- retry/timeouts/idempotency rules;
- safe error normalization;
- audit projection;
- quota/entitlement integration;
- write-approval gating;
- sandbox-only transport tests;
- operator/provider evidence sufficient for the intended connector claim;
- browser/client E2E;
- independent review approval.

## 9. Review gates after sandbox closure

### R1 — qualification evidence review

Review:

- evidence provenance and exact execution commits;
- source/version alignment;
- positive/negative-path coverage;
- sanitized evidence completeness;
- no credential leakage;
- no false operator-network claims.

Output: accept/reject/conditions for sandbox evidence package.

### R2 — provider compatibility governance review

Decide explicitly:

- whether Telefonica v0.10 is merely interoperability evidence;
- whether a separate provider adapter contract is acceptable;
- whether exact CAMARA v1.1.0 provider proof is still mandatory;
- how `retrieveSessionsByDevice` incompatibility is handled.

No compatibility waiver may be inferred from successful four-operation testing.

### R3 — runtime connector design review

Required artifacts:

- connector contract;
- operation bindings;
- managed endpoint references;
- managed secret references;
- auth/token lifecycle;
- timeout/retry/idempotency strategy;
- approval/entitlement/quota enforcement;
- telemetry/audit/redaction rules;
- rollback/kill-switch behavior;
- sandbox-only execution tests.

Output may approve a sandbox connector candidate only. Production remains separate.

### R4 — security/privacy review

Must cover:

- device identifiers / phone numbers;
- network/application server addresses;
- access tokens and client credentials;
- log redaction;
- data retention;
- least privilege/scopes;
- credential rotation/revocation;
- outbound allowlisting;
- callback/webhook exposure if later enabled;
- abuse/rate-limit controls.

### R5 — client/UI E2E review

Must prove:

- server state and UI state agree;
- all blocked/approved states are rendered correctly;
- no UI control can bypass server authority;
- accessibility and responsive checks pass;
- browser flows preserve authentication/authorization boundaries.

### R6 — staging readiness review

Only after the previous reviews pass.

Required:

- non-production staging environment;
- isolated staging credentials;
- exact endpoint allowlist;
- controlled test subjects;
- monitoring/alerts;
- rollback and kill switch;
- quota/cost controls;
- end-to-end audit trail;
- no production data by default;
- explicit staging authorization.

### R7 — release candidate review

Required:

- repository reconciliation;
- full CI green at exact release-candidate SHA;
- dependency/security review;
- packaging/versioning;
- migration/rollback validation;
- operator/provider evidence accepted;
- connector qualification decision recorded;
- unresolved blockers zero or explicitly accepted by authorized governance.

### R8 — controlled production pilot

Not currently authorized.

Requires a separate explicit decision after staging qualification, including:

- production credentials;
- operator production agreement/entitlement;
- production endpoint allowlist;
- strict user/traffic cohort;
- budgets/quotas;
- incident response ownership;
- rollback/disable control;
- monitoring/SLOs;
- compliance/privacy approval;
- explicit production pilot approval.

### R9 — GA

Not currently authorized.

Requires pilot success, operational readiness, support ownership, commercial/contractual readiness, security/privacy acceptance, capacity/SLO validation, and an explicit GA decision.

## 10. Broader program roadmap after CAMARA closure

The previously defined program sequence remains:

```text
AUTH-R9B
→ AUTH-R9C
→ AUTH-R9D
→ AUTH-R10
→ ADMIN-MARKET-R1 … R10
→ QUOTAS-R1 … R4
→ PRICING-R1 … R4
→ Repository reconciliation
→ Packaging
→ Real staging
→ Release candidate
→ Controlled production pilot
→ GA
```

These phases must not use the Telefonica mock result as a substitute for the qualification gates described above.

## 11. Immediate next-action queue

Priority order:

1. Correct Integration Center CAMARA rendering to the current server contract and add tests for Approved + Registered/default-deny + external-evidence-separated state.
2. Investigate an exact/current provider surface for `retrieveSessionsByDevice`; if absent, document incompatibility and submit it to governance review.
3. Add controlled negative-path Telefonica sandbox probes and retain sanitized evidence.
4. Determine availability of a real operator-backed QoD sandbox/test environment and required test number/device eligibility.
5. Complete browser/client E2E and accessibility/responsive validation.
6. Perform the qualification evidence review and provider compatibility governance review.
7. Only then propose a provider-specific sandbox connector contract for review.

## 12. Handoff invariants

Any successor must preserve these invariants:

- keep PR #163 Draft unless explicitly authorized otherwise;
- do not merge, rebase, force-push, enable auto-merge, or mark ready without explicit authorization;
- do not commit or paste provider secrets/tokens;
- do not modify the approved CAMARA semantic blob silently;
- do not set `provider_sandbox_proven=true` for CAMARA v1.1.0 based on Telefonica v0.10 mock evidence;
- do not set `operator_network_qos_proven=true` without non-mock network evidence;
- do not set `runtime_connector_approved=true` without an independently reviewed provider connector contract;
- keep `production_allowed=false` until a separate explicit production authorization;
- distinguish standards-source proof, mock interoperability proof, operator-network proof, connector approval, staging approval, and production approval as separate gates.
