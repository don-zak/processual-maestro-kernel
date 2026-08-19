# CAMARA QoD Governance Decision R1

## Status

**Decision state: PENDING / REVIEW REQUIRED**

This document defines the exact governance decision boundary for the reviewed CAMARA Quality on Demand contract. It is a review packet, not an approval record.

Until an authorized governance decision is explicitly recorded against the exact contract version below:

- `governance_approved=false`;
- `runtime_task_registered=false`;
- `runtime_connector_approved=false`;
- `provider_sandbox_proven=false`;
- `production_allowed=false`.

No statement in this document grants runtime, provider, staging, or production authority.

## Exact candidate contract version

The governance candidate is bound to the following immutable implementation state:

- repository: `don-zak/processual-maestro-kernel`;
- implementation commit: `6898bbdbaefa765b3d1f692742c8f812e7743a94`;
- contract file: `processual_api/integrations/camara_qod_semantic_mapping.py`;
- contract blob SHA: `70d57dd3d8c9632c7e45260646c71049cbbc1cee`;
- source identity: `camara.quality_on_demand.r3_2`;
- CAMARA source revision: `9cb179fd3b63f43d564c76689295cd681e723548`;
- CAMARA API version: `1.1.0`.

For governance purposes, the candidate version identifier is:

`camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`

Any change to the task IDs, operation classes, entitlement IDs, quota meters, approval requirements, CAMARA operation IDs, HTTP methods, paths, or security scopes requires a new review version. Approval of a near-match or later unreviewed version must not be inferred from approval of this candidate.

## Candidate task contracts

| CAMARA operation | Maestro task candidate | Semantic class | Approval required | Entitlement | Quota meter |
| --- | --- | --- | --- | --- | --- |
| `createSession` | `camara.qod.session_create` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_create` |
| `getSession` | `camara.qod.session_get` | `read` | no | `camara_qod_session_read` | `camara_qod_session_read` |
| `deleteSession` | `camara.qod.session_delete` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_delete` |
| `extendQosSessionDuration` | `camara.qod.session_extend` | `approval_gated_write` | yes | `camara_qod_session_manage` | `camara_qod_session_update` |
| `retrieveSessionsByDevice` | `camara.qod.sessions_retrieve_by_device` | `read` | no | `camara_qod_session_read` | `camara_qod_session_retrieve_by_device` |

`postNotification` is not a Maestro outbound task. It remains excluded as a provider-to-consumer callback.

## Entitlement candidates

The exact entitlement candidate set is:

1. `camara_qod_session_manage`;
2. `camara_qod_session_read`.

These identifiers are not authoritative runtime grants until this exact candidate version receives explicit governance approval and the separately controlled runtime-registration step is implemented.

## Quota meter candidates

The exact quota-meter candidate set is:

1. `camara_qod_session_create`;
2. `camara_qod_session_delete`;
3. `camara_qod_session_read`;
4. `camara_qod_session_retrieve_by_device`;
5. `camara_qod_session_update`.

Approval of these names does not by itself define commercial limits or grant plan entitlements. Runtime accounting and plan binding remain separate implementation and policy steps.

## Required governance assertions

An approval of this candidate must explicitly confirm all of the following:

1. The five task IDs above are the approved Maestro semantic boundary for CAMARA QoD v1.1.0.
2. `createSession`, `deleteSession`, and `extendQosSessionDuration` are state-changing operations and must remain approval-gated writes.
3. `getSession` and `retrieveSessionsByDevice` are read semantics; `retrieveSessionsByDevice` remains a read despite using HTTP POST for complex/sensitive device input.
4. The two entitlement IDs and five quota-meter IDs above are approved governance identifiers for later runtime registration.
5. Two-legged and three-legged subject rules remain enforced as represented in the reviewed semantic mapping.
6. Device identifiers may constitute personal data and must remain classified accordingly.
7. Notification credentials must be represented only by managed credential references; raw notification secrets must not be persisted in task state.
8. Approval is limited to this exact candidate version and does not approve an operator/provider endpoint, credentials, network access, connector execution, staging use, or production use.
9. Runtime registration is a later, separately reviewable action and must remain fail-closed/default-deny until implemented and tested.
10. Provider qualification, external request/response proof, browser E2E, and production authorization remain independent gates.

## Evidence already available

The reviewed public CAMARA source has live local qualification evidence at execution commit `f1595583ee573942d7ae131ec3572a863805c25e` for the same pinned CAMARA source revision, including:

- `source_identity_verified=true`;
- `external_references_resolved=true`;
- `discovery_quality_passed=true`;
- `semantic_mapping_aligned=true`;
- `public_source_qualification_ready=true`;
- source SHA-256 `e67849832ac08f14634174c26f0f3634e8fcfe16922d6cd3bd0ccb394d410ff9`;
- bundle SHA-256 `adc0d4c1c1ef85d63deebbefd3807a447d4560baef2e5458da4a2ea1e0a66c60`.

That evidence proves public-source acquisition and semantic alignment at its stated execution commit. It does not constitute this governance decision and does not prove provider/operator sandbox access.

Current-head CI is separately responsible for proving the governance-candidate validation/status/UI contracts added after that live execution.

## Decision record

The fields below must be completed by an authorized governance decision. Leaving them blank means the decision remains pending.

- decision: `PENDING`
- approved candidate version: `PENDING`
- authorized approver / authority reference: `PENDING`
- decision timestamp: `PENDING`
- decision evidence reference: `PENDING`
- conditions or exceptions: `PENDING`

### Approval rule

Only an explicit decision that identifies
`camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`
and affirmatively approves the required governance assertions above may transition governance state to approved.

Absence of a decision, a generic PR approval, CI success, source qualification success, or internal candidate validity must not be interpreted as `governance_approved=true`.

## Exit condition for CAMARA-CLOSE-1

CAMARA-CLOSE-1 is complete only when all of the following are true:

- the exact candidate version is explicitly approved by authorized governance;
- the decision record is auditable and names the approving authority/evidence;
- `governance_approved=true` is backed by that explicit decision;
- no runtime task is implicitly registered as a side effect of approval.

Only after that exit condition is met may CAMARA-CLOSE-2 begin: registering the approved tasks, entitlement identifiers, and quota meters behind default-deny/fail-closed runtime controls while keeping provider and production authority false.