# CAMARA QoD Runtime Registration R1

## Purpose

Record CAMARA-CLOSE-2 for the exact governance-approved CAMARA Quality on Demand contract without granting provider connector or production authority.

## Governance dependency

Runtime registration is bound to:

- approved governance version: `camara-qod-governance-r1@70d57dd3d8c9632c7e45260646c71049cbbc1cee`;
- approved semantic contract blob: `70d57dd3d8c9632c7e45260646c71049cbbc1cee`;
- governance decision: `APPROVED_WITH_CONDITIONS`;
- CAMARA source revision: `9cb179fd3b63f43d564c76689295cd681e723548`;
- API version: `1.1.0`.

Any drift in the approved task, entitlement, quota, operation, path, method, or scope contract requires a new governance review rather than implicit inheritance.

## Registered task set

The dedicated CAMARA QoD runtime registry contains exactly five registrations:

1. `camara.qod.session_create` -> `createSession` -> `POST /sessions` -> approval-gated write;
2. `camara.qod.session_get` -> `getSession` -> `GET /sessions/{sessionId}` -> read;
3. `camara.qod.session_delete` -> `deleteSession` -> `DELETE /sessions/{sessionId}` -> approval-gated write;
4. `camara.qod.session_extend` -> `extendQosSessionDuration` -> `POST /sessions/{sessionId}/extend` -> approval-gated write;
5. `camara.qod.sessions_retrieve_by_device` -> `retrieveSessionsByDevice` -> `POST /retrieve-sessions` -> read semantic.

`postNotification` remains excluded because it is a provider-to-consumer callback.

## Registered entitlement identifiers

- `camara_qod_session_manage`;
- `camara_qod_session_read`.

Registration of an entitlement identifier is not assignment of that entitlement to a customer or plan.

## Registered quota meters

- `camara_qod_session_create`;
- `camara_qod_session_delete`;
- `camara_qod_session_read`;
- `camara_qod_session_retrieve_by_device`;
- `camara_qod_session_update`.

Registration of a quota-meter identifier does not establish a commercial limit. Plan binding and accounting limits remain separate policy.

## Default-deny admission

`assess_camara_qod_runtime_admission()` denies execution unless all required evidence is present for the requested task.

Every task requires:

- the exact registered entitlement;
- explicit quota evidence with remaining quota greater than zero;
- provider sandbox proof;
- runtime connector approval.

State-changing tasks additionally require an explicit approval reference:

- `createSession`;
- `deleteSession`;
- `extendQosSessionDuration`.

Unknown task IDs fail closed. Registration construction also fails if the task, entitlement, or quota sets drift from the exact governance-approved sets.

## Authority separation

After runtime registration:

- `governance_approved=true`;
- `runtime_task_registered=true`;
- `runtime_default_deny=true`;
- `runtime_connector_approved=false`;
- `provider_credentials_present=false`;
- `provider_network_proof=false`;
- `provider_sandbox_proven=false`;
- `production_allowed=false`.

A registered task is therefore a known governed runtime contract, not permission to make an external request.

## Why the registry is dedicated

The approved semantic candidate remains immutable review evidence and deliberately tests that its proposed task IDs were not already present in the pre-approval generic integration task catalog. Rewriting that approved candidate after approval would weaken auditability.

CAMARA-CLOSE-2 therefore uses a dedicated registry bound to the approved contract version. This keeps the three facts distinct:

1. semantic/governance contract approved;
2. runtime task registered;
3. provider connector execution approved.

Only the first two are true at this stage.

## Test evidence

`tests/test_camara_qod_runtime_registration.py` covers:

- exact approved governance version;
- exact five task registrations;
- exact two entitlement identifiers;
- exact five quota meters;
- preservation of write approval gating;
- default denial without entitlement/quota/provider/connector evidence;
- denial of writes without approval reference;
- denial on exhausted quota;
- unknown-task fail-closed behavior;
- continued `production_allowed=false` even when sandbox admission inputs are synthetically complete.

`tests/test_camara_qod_qualification_status_route.py` separately verifies that the safe admin projection exposes governance approval and runtime registration without exposing secrets or claiming provider/production authority.

## CAMARA-CLOSE-2 exit condition

CAMARA-CLOSE-2 is complete when current-head CI proves the registration and default-deny contracts above.

Completion of CAMARA-CLOSE-2 does **not** set `runtime_connector_approved=true`, `provider_sandbox_proven=true`, `CAMARAConnectorQualified=true`, or `production_allowed=true`.

The next closure stage is real operator/channel-partner sandbox qualification with managed credentials and explicit network/provider evidence.