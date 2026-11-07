# External Evaluation Qualification — Closeout

**State date:** 2026-09-12  
**Repository:** `don-zak/processual-maestro-kernel`  
**Working branch:** `feat/evaluation-key-delivery-lifecycle`  
**Qualified public baseline:** `6f7dd018737151cd1906be068f2478d02d19392b`  
**External Evaluation Authority service:** `srv-dag784p594qs73evdshg`  
**Qualified Render deploy:** `dep-daijg768h83s739n8370`  
**Qualification result:** `Q1–Q10 PASS`

This document closes the qualification round that superseded the earlier pause handoff. It pins the exact code/deploy/proof baseline that completed the External Evaluation foundation. Later commits do **not** inherit this qualification automatically; they must be evaluated by impact and requalified where required.

## 1. Qualified baseline

The exact qualified public head is:

`6f7dd018737151cd1906be068f2478d02d19392b`

Render deployed that exact commit on `processual-maestro-external-evaluation-authority` as:

`dep-daijg768h83s739n8370`

The deploy reached `live` after being triggered by the exact qualified commit.

## 2. Exact-head public workflow proof

The following GitHub Actions runs completed successfully on `6f7dd018737151cd1906be068f2478d02d19392b`:

- Branch Protection CI — `34691281253` — success
- Dependency Census — `34691281247` — success
- Security Scan — `34691281238` — success
- A5 Auth and API-Key Authority Qualification — `34691281221` — success
- Security Hardening — `34691281265` — success
- Pre-External Operational Readiness — `34691281232` — success
- Deep Integrity Audit — `34691281276` — success
- CI (Public) — `34691281228` — success
- CI (Private monorepo) — `34691281215` — skipped in the public repository by design

The isolated PostgreSQL quota-boundary/concurrency qualification is wired into `Pre-External Operational Readiness` and is part of the exact-head green proof.

## 3. Q1–Q10 closeout

- **Q1 — Policy / Authority:** PASS
- **Q2 — Fresh Grant + one-time key handoff:** PASS
- **Q3 — Workspace status / zero-quota read:** PASS
- **Q4 — First admitted sandbox execution:** PASS
- **Q5 — Durable replay / +0 quota:** PASS
- **Q6 — Idempotency conflict / +0 quota:** PASS
- **Q7 — Individual key revocation:** PASS
- **Q8 — Grant revocation cascade:** PASS
- **Q9 — Final durable audit:** PASS
- **Q10 — Isolated PostgreSQL concurrency / exhaustion boundary:** PASS

Qualification execution:

- execution id: `exec_0f303bcee10d4a3ba3c633aaec2ce951`
- task: `crm.customer_context`
- binding: `evaluation.crm.customer_context.owned`
- evidence sha256: `912d81c577fd652a417df1b10468c35ac4abe66c93c247638f07e68ab770ed19`
- admitted quota used: `1`
- production execution: `disabled`

Qualification authority artifacts are retained for audit only and are revoked. They must not be reused for later execution qualification.

## 4. Project-owned sandbox proof

The current CRM proof target is the project-owned Cloudflare Worker:

`https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev`

Relevant repository implementation:

- `deployment/evaluation-owned-sandbox/cloudflare/worker.js`
- `deployment/evaluation-owned-sandbox/cloudflare/wrangler.jsonc`

The old Render public sandbox is not the authoritative CRM proof target for this closeout.

## 5. Invariants preserved by qualification

The following are baseline invariants and must not be weakened by follow-up work:

- PostgreSQL-backed authority remains authoritative.
- Policy / Authority → Admission → Execution → Evidence remains the control sequence.
- External Evaluation does not require a commercial subscription.
- CRM quota is 100 admitted executions; Integration quota is 200.
- Status/authentication reads consume +0 quota.
- Durable replay consumes +0 quota.
- Idempotency conflict consumes +0 quota.
- A new admitted execution consumes +1 quota transactionally.
- Production execution remains disabled for External Evaluation.
- Raw Evaluation keys are one-time and are not persisted for redisplay.
- Raw task input and raw downstream response do not belong in durable customer evidence.
- Individual key revocation is immediate.
- Grant revocation cascades to linked active keys.
- Audit/evidence remains reviewable after revocation.
- Browser storage is not an authority source.

## 6. What this closeout does not certify

This closeout does not by itself certify:

- production rollout readiness;
- customer-specific production integration;
- compliance certification;
- high-scale production capacity;
- private-monorepo synchronization;
- commercial/buyer-readiness of the presentation layer.

Those remain separate workstreams.

## 7. Follow-up change policy

Before any follow-up commit, classify the change:

- **copy/CSS/presentation-only:** focused UI regression is normally sufficient;
- **client request/origin/hosting behavior:** add browser/API contract and security regression, plus live origin verification;
- **grant/key/authority/quota/idempotency/runtime/audit/persistence/sandbox-provider semantics:** reopen the affected Q1–Q10 stages and use a fresh qualification grant when execution semantics are affected.

Do not describe a later branch head as qualified merely because it descends from `6f7dd018...`.

## 8. Next approved workstream

The next approved workstream is External Workspace proof-narrative and hosting preparation:

1. preserve the qualified backend/runtime baseline;
2. make the workspace buyer-readable while keeping technical evidence available on demand;
3. prepare the client for a Zaxam Tech customer-facing origin without moving authority into the marketing site;
4. keep API credentials memory-only and prevent third-party scripts/storage from receiving them;
5. add regression coverage for origin configuration, authority-derived scenarios, quota semantics, revocation/locked presentation, and safe reports;
6. then expand CRM Summary / CRM Draft / Integration scenarios;
7. review Admin/API-key UX and obsolete files;
8. synchronize the private repository only through guarded staging and executable private CI.
