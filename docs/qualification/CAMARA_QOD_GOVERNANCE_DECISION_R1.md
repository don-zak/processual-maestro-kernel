# CAMARA QoD Governance Decision R1

## Status

**Decision state: APPROVED WITH CONDITIONS**

This decision approves the reviewed CAMARA Quality on Demand governance contract at the exact immutable candidate version identified below. The approval is limited to the task, entitlement, quota, identity, data-classification, and approval-gating contract. It does not approve a provider connector, provider credentials, staging use, or production use.

Current authority boundaries after this decision:

- `governance_approved=true`;
- `runtime_task_registered=false` until CAMARA-CLOSE-2 implementation is proven;
- `runtime_connector_approved=false`;
- `provider_sandbox_proven=false`;
- `production_allowed=false`.

## Exact approved contract version

- repository: `don-zak/processual-maestro-kernel`;
- candidate implementation commit: `6898bbdbaefa765b3d1f692742c8f812e7743a94`;
- contract file: `processual_api/integrations/camara_qod_semantic_mapping.py`;
- approved contract blob SHA: `70d57dd3d8c9632c7e45260646c71049cbbc1cee`;
- approved governance version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`;
- source identity: `camara.quality_on_demand.r3_2`;
- CAMARA source revision: `9cb179fd3b63f43d564c76689295cd681e723548`;
- CAMARA API version: `1.1.0`.

Any change to task IDs, operation classes, entitlement IDs, quota meters, approval requirements, CAMARA operation IDs, HTTP methods, paths, or security scopes requires a new governance review/version. Approval must not be inherited by a near-match or later unreviewed contract.

## Approved task contracts

| CAMARA operation | Maestro task | Semantic class | Approval required | Entitlement | Quota meter |
| --- | --- | --- | --- | --- | --- |
| `createSession` | `camara.qod.session_create` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_create` |
| `getSession` | `camara.qod.session_get` | `read` | no | `camara_qod_session_read` | `camara_qod_session_read` |
| `deleteSession` | `camara.qod.session_delete` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_delete` |
| `extendQosSessionDuration` | `camara.qod.session_extend` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_update` |
| `retrieveSessionsByDevice` | `camara.qod.sessions_retrieve_by_device` | `read` | no | `camara_qod_session_read` | `camara_qod_session_retrieve_by_device` |

`postNotification` remains excluded from Maestro outbound binding because it is a provider-to-consumer callback.

## Approved entitlement identifiers

1. `camara_qod_session_manage`;
2. `camara_qod_session_read`.

Approval of these identifiers does not grant them to any customer or plan. Runtime entitlement assignment remains separately controlled.

## Approved quota-meter identifiers

1. `camara_qod_session_create`;
2. `camara_qod_session_delete`;
3. `camara_qod_session_read`;
4. `camara_qod_session_retrieve_by_device`;
5. `camara_qod_session_update`.

Approval of these identifiers does not define commercial limits. Runtime accounting and plan binding remain separate controls.

## Governance assertions approved

The decision affirms all of the following:

1. The five task IDs above are the approved Maestro semantic boundary for CAMARA QoD v1.1.0.
2. `createSession`, `deleteSession`, and `extendQosSessionDuration` remain approval-gated writes.
3. `getSession` and `retrieveSessionsByDevice` remain read semantics; the latter is a read despite HTTP POST because POST carries complex/sensitive device input rather than a state mutation.
4. The two entitlement IDs and five quota-meter IDs above are approved governance identifiers for runtime registration.
5. Two-legged and three-legged subject rules remain enforced as represented in the reviewed semantic mapping.
6. Device identifiers remain classified as possible personal data.
7. Notification credentials must be represented only by managed credential references; raw notification secrets must not be persisted in task state.
8. This approval does not approve an operator/provider endpoint, credentials, network access, connector execution, staging use, or production use.
9. Runtime registration is a separate step and must be fail-closed/default-deny with entitlement, quota, drift, and approval gating proven before execution.
10. Provider qualification, external request/response proof, browser E2E, and production authorization remain independent gates.

## Evidence basis

The reviewed public CAMARA source has live local qualification evidence at execution commit `f1595583ee573942d7ae131ec3572a863805c25e` for the same pinned CAMARA revision, including:

- `source_identity_verified=true`;
- `external_references_resolved=true`;
- `discovery_quality_passed=true`;
- `semantic_mapping_aligned=true`;
- `public_source_qualification_ready=true`;
- source SHA-256 `e67849832ac08f14634174c26f0f3634e8fcfe16922d6cd3bd0ccb394d410ff9`;
- bundle SHA-256 `adc0d4c1c1ef85d63deebbefd3807a447d4560baef2e5458da4a2ea1e0a66c60`.

Current-head CI separately proves the governance-candidate validation/status/UI contracts. The live-source evidence does not prove provider/operator sandbox access.

## Decision record

- decision: `APPROVED_WITH_CONDITIONS`
- approved candidate version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`
- authority reference: explicit repository-owner/user instruction in the active work session following technical governance review of the exact candidate and tests
- decision timestamp: `2026-08-19T06:23:00+01:00`
- decision evidence reference: PR #163 governance review trail plus this committed decision record
- conditions: runtime/provider/staging/production authority remain closed as listed above

## CAMARA-CLOSE-1 exit

CAMARA-CLOSE-1 is **complete** for the exact approved governance version above. No runtime task is registered as a side effect of this approval.

CAMARA-CLOSE-2 may now proceed: register the exact approved tasks, entitlement identifiers, and quota meters behind default-deny/fail-closed controls while keeping `runtime_connector_approved=false`, `provider_sandbox_proven=false`, and `production_allowed=false`.