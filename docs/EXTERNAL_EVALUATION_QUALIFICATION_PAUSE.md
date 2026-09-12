# External Evaluation Qualification — Pause Handoff

**State date:** 2026-09-11  
**Repository:** `don-zak/processual-maestro-kernel`  
**Working branch:** `feat/evaluation-key-delivery-lifecycle`  
**Functional qualification baseline at pause:** `55b7c489f943f4f614fef7a458c75eb9b89fd428`

This document intentionally pins the exact operational state at the point where live External Evaluation qualification was paused because the project-owned sandbox proof repeatedly received downstream HTTP `429`. The pause is an infrastructure/capacity constraint under the currently available free hosting resources; it is not permission to weaken qualification gates or bypass the live proof.

## 1. Proven baseline

At the functional baseline above:

- all relevant public CI/security/readiness gates are green;
- `CI (Private monorepo)` is skipped in the public repository as expected;
- the External Evaluation Authority deploy is Live on the exact functional baseline;
- Authority `GET /health/live` was proven live;
- the project-owned sandbox `GET /users/1` was manually proven to return the deterministic synthetic customer payload;
- Q1 is therefore considered passed for this qualification round;
- the prepared-Evaluation-binding UI selection-loss defect was repaired and regression-covered;
- the owned CRM preset now has bounded retry for transient `sandbox_http_status_not_allowed:429`: maximum three attempts with 1s then 2s backoff, and no retry widening to other failures.

The pause document is documentation-only. Before resuming live qualification, always re-check the current branch head, CI, and Render exact-head state rather than assuming this historical baseline is still the deployed head.

## 2. Current blocker

The live Admin flow repeatedly reaches:

`Prepare & prove CRM-CONTEXT-01`

and fails with:

`sandbox_http_status_not_allowed:429`

The fixed owned proof target remains:

- base URL: `https://processual-maestro-kernel.onrender.com`
- method/path: `GET /users/1`
- binding: `evaluation.crm.customer_context.owned`
- task: `crm.customer_context`
- expected success code: `200`
- production: disabled

The owned sandbox application contract itself defines `/users/1` as a deterministic HTTP 200 read endpoint. The hardened Maestro executor simply surfaces an unexpected downstream HTTP status. The failed proof requests were not established as application-generated 429 responses, so the exact upstream/front-door source of the persistent 429 remains unproven. Do not overstate the root cause.

Operator decision: stop repeated live attempts and wait for free hosting capacity/quota to become available. There is currently no international payment method available for upgrading the hosting plan.

## 3. Authority state deliberately not advanced

During this qualification round:

- no new Evaluation Grant was created after the current blocker;
- no new Evaluation API key was issued;
- Q4 was not entered;
- admitted-execution quota consumption remains `0` for the intended new qualification Grant;
- no workaround was used to mark the binding selectable after a failed live proof.

An older pre-existing Grant named `zaxam` is visible in Admin (`active · CRM`, quota 100, two active keys). It is historical state and **must not be reused as the clean qualification Grant** for the resumed Q2–Q9 sequence.

## 4. Exact resume point

When free hosting capacity becomes usable again:

1. verify branch head and all relevant CI gates;
2. verify the exact current head is Live on the Authority service;
3. hard-refresh Admin, authenticate, and perform fresh MFA;
4. select External Evaluation / CRM and the intended operational profile;
5. select canonical CRM task(s) required for the clean qualification scenario;
6. select only `POST /evaluation/runtime/task-execute` for the first runtime proof and verify derived scope `run:evaluation`;
7. run `Prepare & prove CRM-CONTEXT-01` once;
8. require `CRM-CONTEXT-01 READY` and authoritative catalog state `sandbox_ready · selectable`;
9. select `evaluation.crm.customer_context.owned` and wait 10–15 seconds to verify the checkbox remains selected and `Create Evaluation Grant` remains ready across rerenders;
10. only then create a **new** explicit CRM Evaluation Grant and continue the runbook.

Do not create a Grant or issue a key while the prepared binding is locked or while the owned live proof is failing.

## 5. Remaining qualification sequence

- **Q2:** clean CRM Grant authority + one-time API-key issue + safe handoff + delivery/receipt evidence. No execution quota consumed.
- **Q3:** customer `/console/evaluation.html` status/dashboard proof. Expect `0/100` used.
- **Q4:** exactly one fresh admitted execution. Expect `1/100` used.
- **Q5:** exact replay with same idempotency key/input. Expect `+0` quota.
- **Q6:** same idempotency key with changed input. Expect HTTP `409` and `+0` quota.
- **Q7:** individual key revocation; sibling key isolation if a sibling is intentionally issued for that proof.
- **Q8:** Grant revocation rejects every linked key before admission.
- **Q9:** administrator final audit with `qualification_decision=operator_required`; no automatic final verdict.
- **Q10:** concurrency/exhaustion proof remains isolated PostgreSQL integration testing only. Never burn 100/200 live evaluation units to prove exhaustion.

## 6. Semantics that must remain invariant

- PostgreSQL Evaluation authority remains authoritative.
- Grant authority is stronger than API-key metadata; a key cannot widen the Grant.
- CRM qualified quota is 100 admitted executions; Integration is 200.
- authentication, status reads and durable replay do not consume quota.
- one new admitted execution consumes one unit even if downstream execution later becomes uncertain.
- production remains disabled throughout External Evaluation.
- no raw API key, customer credential, raw task input, or raw downstream payload belongs in evidence/logging.
- sandbox/browser/delivery acknowledgement never grant or widen runtime authority.

## 7. Resume completion definition

Do not describe External Evaluation as fully operationally qualified until the runbook's Q1–Q9 live proof is complete on the intended exact head and Q10 remains green in isolated PostgreSQL qualification.

The next unrelated workstream may proceed while this live qualification is paused, provided no one silently treats the pause as a qualification pass.