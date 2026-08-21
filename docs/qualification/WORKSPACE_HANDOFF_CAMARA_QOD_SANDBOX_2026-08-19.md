# Workspace Handoff — CAMARA QoD Sandbox Qualification — 2026-08-19

## Purpose

This document is the authoritative handoff for continuing CAMARA Quality on Demand sandbox qualification work in a new workspace. It summarizes completed implementation, evidence, current blockers, exact authority boundaries, and the remaining review/qualification roadmap through staging, release candidate, controlled production pilot, and GA.

## Repository / PR state

- Repository: `don-zak/processual-maestro-kernel`
- Branch: `agent/settings-sandbox-qualification-r1`
- PR: `#163` — `test: establish settings sandbox qualification baseline`
- Base: `agent/admin-governance-foundation`
- Verified current state before this handoff: open, draft, unmerged, mergeable
- Never mark Ready, merge, rebase, force-push, enable auto-merge, or grant production/runtime authority without explicit authorization.

## Immutable governed CAMARA contract

- Source identity: `camara.quality_on_demand.r3_2`
- CAMARA QoD API version: `1.1.0`
- Source revision: `9cb179fd3b63f43d564c76689295cd681e723548`
- Source path: `code/API_definitions/quality-on-demand.yaml`
- Approved semantic blob: `70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- Governance version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- Governance decision: `approved_with_conditions`

Approved outbound operations:

1. `createSession` → `camara.qod.session_create`
2. `getSession` → `camara.qod.session_get`
3. `deleteSession` → `camara.qod.session_delete`
4. `extendQosSessionDuration` → `camara.qod.session_extend`
5. `retrieveSessionsByDevice` → `camara.qod.sessions_retrieve_by_device`

`postNotification` is excluded from outbound binding because it is a provider callback.

## Completed implementation

### Public-source qualification

The pinned CAMARA source was acquired and semantically qualified. Retained proof records source identity, external reference resolution, discovery quality, semantic alignment, and immutable digests. Public-source proof is standards evidence only and does not imply provider execution.

### Governance approval

The five tasks, two entitlements, and five quota meters are approved for the exact reviewed semantic blob. Governance approval does not grant credentials, provider network access, runtime connector execution, staging, or production.

### Runtime registration

`processual_api/integrations/camara_qod_runtime_registration.py` registers the exact five approved tasks with default-deny admission. Admission requires entitlement, positive quota evidence, write approval where applicable, governed provider sandbox proof, and runtime connector approval.

### Operator intake / offline preparation

Implemented:

- `processual_api/integrations/camara_qod_operator_sandbox_intake.py`
- `tools/camara_qod_operator_sandbox_qualify.ps1`
- `tools/camara_qod_offline_precheck.ps1`

Offline evidence retained at:

`docs/qualification/evidence/CAMARA_QOD_OFFLINE_PRECHECK_2026-08-19.json`

### Telefonica Open Gateway external sandbox/mock evidence

Registered sandbox application authentication succeeded via CIBA.

Observed successful calls:

```text
POST /bc-authorize                            -> 200
POST /token                                   -> 200
POST /qod/v0/sessions                         -> 201
GET  /qod/v0/sessions/{createdSessionId}      -> 200
POST /qod/v0/sessions/{sessionId}/extend      -> 200
DELETE /qod/v0/sessions/{sessionId}           -> 204
```

Working sandbox base discovered from the interactive reference:

`https://sandbox.opengateway.telefonica.com/apigateway/qod/v0`

The earlier `/apigateway/ogw/qod/v0` route returned 404 in the live sandbox application path and is not used by the working probes.

Retained sanitized lifecycle evidence:

`docs/qualification/evidence/TELEFONICA_QOD_CIBA_SESSION_LIFECYCLE_2026-08-19.json`

No client secret, access token, auth request ID, or session ID is retained in repository evidence.

### Telefonica negative-path evidence

Controlled tests observed:

```text
invalid duration                         -> 400  expected
missing Authorization                    -> 401  expected
documented deterministic mock conflict   -> 409  expected
fresh never-created session UUID          -> 200  divergence; reference documents 404
```

The missing-session 200 was reproduced with a fresh random UUID that was never passed to `createSession`, so it is retained as a confirmed sandbox/mock documentation divergence rather than normalized into conformance.

Evidence:

`docs/qualification/evidence/TELEFONICA_QOD_MISSING_SESSION_DIVERGENCE_2026-08-19.json`

Current compatibility state:

`partial_interoperability_with_negative_path_divergence`

### Telefonica `retrieveSessionsByDevice` decision

The current Telefonica Open Gateway documentation index enumerates the QoD v0.10 surface as QoS-profile lookup plus create/check/cancel/extend session operations. It does not enumerate `/retrieve-sessions` or a `retrieveSessionsByDevice` operation.

Decision record:

`docs/qualification/TELEFONICA_QOD_RETRIEVE_SESSIONS_BY_DEVICE_DECISION_2026-08-19.md`

Therefore the operation is classified as unavailable/unproven on the reviewed Telefonica QoD v0.10 surface. No compatibility waiver is inferred.

### External qualification model

Implemented:

- `processual_api/integrations/camara_qod_external_sandbox_qualification.py`
- `processual_api/integrations/camara_qod_telefonica_compatibility.py`
- `tests/test_camara_qod_telefonica_external_qualification.py`

Four governed operation shapes have positive-path external interoperability evidence:

- `createSession`
- `getSession` for a created session
- `deleteSession`
- `extendQosSessionDuration`

The model explicitly records the missing-session divergence and the absent `retrieveSessionsByDevice` surface.

### Integration Center server projection

`processual_api/routers/settings_camara_qod_qualification_status.py` now projects:

- approved governance state;
- registered runtime tasks/default-deny state;
- governed provider/runtime/production gates;
- external sandbox evidence as a separate non-authoritative object;
- Telefonica compatibility state and blocker codes.

Tests verify that this projection does not upgrade provider/runtime/production authority or expose secrets.

The legacy browser renderer still contains stale text for Governance=Review required and runtime registration disabled. The server truth is now correct; browser rendering remains an explicit S3 closure item.

## Current truthful flags

```text
source_identity_verified=true
semantic_mapping_aligned=true
governance_approved=true
runtime_task_registered=true
runtime_default_deny=true
authenticated_sandbox_reachability_proven=true
external_mock_sandbox_proven=true
external_mock_extend_proven=true
mock_documentation_divergence_observed=true
missing_session_documented_expectation_met=false
negative_path_conformance_complete=false
operator_network_qos_proven=false
governed_camara_v1_1_provider_sandbox_proven=false
provider_sandbox_proven=false
runtime_connector_approved=false
staging_allowed=false
production_allowed=false
CAMARAConnectorQualified=false/ungranted
ExternalApiIntegrationQualified=false/ungranted
```

## Current blockers

```text
telefonica_api_version_differs_from_governed_camara_v1_1
telefonica_retrieve_sessions_by_device_unproven_or_unavailable
telefonica_missing_session_returns_200_instead_of_documented_404
telefonica_negative_path_conformance_incomplete
operator_network_qos_unproven
runtime_connector_unapproved
browser_integration_center_rendering_not_reconciled
browser_client_e2e_not_complete
managed_secret_reference_not_complete
```

## Remaining Sandbox Qualification

### S1 — external evidence closure

Mostly complete for the tested Telefonica mock surface.

Remaining:

- pin exact provider documentation/revision metadata where practical;
- decide governance disposition for missing `retrieveSessionsByDevice`;
- decide governance disposition for the missing-session semantic divergence;
- add any remaining safe idempotency/expiry/error cases if the provider surface supports them without creating unsafe side effects;
- review sanitized evidence package for completeness and provenance.

Exit: every governed operation must be either proven on an acceptable exact provider surface or explicitly classified as unsupported with an approved governance decision.

### S2 — operator-network proof

Not complete.

Need a provider/operator-backed non-mock test environment and evidence that QoS actions are network-backed rather than deterministic mock responses. Required evidence includes operator/environment identity, API version, managed credential references, eligible test device/number, QoS profile availability, create/extend/get/delete behavior, observable provider/network state, and network failure semantics.

### S3 — Integration Center/browser E2E

Partially complete.

Server projection is reconciled. Remaining browser work:

- render Governance as `Approved`;
- render runtime tasks as `Registered / default-deny`;
- show external Telefonica evidence separately as non-authoritative;
- keep provider/runtime/production blocked;
- remove stale `Review required` / `runtime registration disabled` wording;
- add browser/client E2E;
- validate responsive behavior, keyboard navigation, focus behavior, and accessibility.

### S4 — secret management / operations hygiene

Partially complete.

Existing probes use environment variables and do not retain secrets. Before a reusable connector:

- use project-managed secret references;
- implement lookup/rotation/revocation proof;
- define token expiry/refresh behavior;
- define mock/operator/staging environment separation;
- define outbound allowlisting;
- define incident response and credential revocation process.

### S5 — sandbox connector candidate

Not approved.

Required before `runtime_connector_approved=true` may be considered:

- exact provider contract/version pinned;
- explicit capability mapping including unsupported operations;
- approved auth contract;
- managed endpoint and secret references;
- retry/timeout/idempotency rules;
- safe error normalization;
- audit/redaction rules;
- entitlement/quota/write-approval enforcement;
- sandbox-only connector tests;
- evidence and compatibility review;
- browser/client E2E;
- independent design/security review.

## Review and Qualification Plan

### R1 — Qualification Evidence Review

Review evidence provenance, execution commits, versions, positive/negative paths, sanitization, and absence of credential leakage. Output: accept/reject/conditions for the sandbox evidence package.

### R2 — Provider Compatibility Governance Review

Decide whether Telefonica v0.10 remains evidence-only, whether a provider-specific reduced-capability adapter is acceptable, whether an exact CAMARA v1.1.0 provider remains mandatory, and how to handle the missing `retrieveSessionsByDevice` and missing-session divergence.

### R3 — Runtime Connector Design Review

Review connector contract, operation mappings, auth/token lifecycle, endpoint/secret references, retries/timeouts/idempotency, error normalization, quota/entitlement/approval gates, telemetry/audit/redaction, kill switch, and rollback.

### R4 — Security & Privacy Review

Cover phone/device identifiers, network/application-server addresses, OAuth tokens, credentials, least privilege, retention, redaction, rotation/revocation, outbound allowlisting, callbacks, abuse/rate limiting, and incident response.

### R5 — Browser/UI E2E Review

Prove server/UI agreement, blocked/approved states, no client-side authority bypass, accessibility, responsive layout, keyboard/focus behavior, and safe authentication/authorization boundaries.

### R6 — Staging Readiness Review

Requires isolated staging credentials, exact endpoint allowlist, controlled test subjects, monitoring/alerts, rollback/kill switch, quota/cost controls, full audit trail, no production data by default, and explicit staging authorization.

### R7 — Release Candidate Review

Requires repository reconciliation, full CI green at the exact RC SHA, dependency/security review, packaging/versioning, migration/rollback validation, accepted provider/operator evidence, connector qualification decision, and zero unresolved blockers unless explicitly accepted by authorized governance.

### R8 — Controlled Production Pilot

Not authorized.

Requires separate explicit approval, production credentials, operator production entitlement, production endpoint allowlist, strict traffic cohort, budgets/quotas, monitoring/SLOs, incident ownership, rollback/disable controls, security/privacy approval, and explicit production-pilot authorization.

### R9 — GA

Not authorized.

Requires pilot success, support and operational ownership, commercial/contractual readiness, security/privacy acceptance, capacity/SLO validation, and explicit GA approval.

## Broader roadmap after CAMARA closure

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

## New workspace immediate queue

1. Verify current PR #163 remains Open + Draft + unmerged and re-check CI for the exact latest HEAD.
2. Complete Integration Center browser-rendering reconciliation and update UI contract tests.
3. Review and formally disposition the Telefonica v0.10 capability gap and missing-session divergence through R2 governance.
4. Locate/obtain an operator-backed non-mock QoD test environment; do not infer network proof from mock success.
5. Complete browser/client E2E and accessibility/responsive checks.
6. Prepare managed endpoint/secret/auth connector design without enabling runtime execution.
7. Run R1 evidence review and R2 compatibility governance review before proposing connector approval.

## Security note

Never paste or commit provider client secrets or access tokens. Previously exposed GSMA token material must not be reused. Telefonica credentials must stay outside repository evidence and should be rotated if any real secret is accidentally disclosed.

## Handoff invariant

External mock interoperability, governed provider proof, operator-network proof, runtime connector approval, staging approval, production pilot approval, and GA are separate gates. None may be inferred from another.
