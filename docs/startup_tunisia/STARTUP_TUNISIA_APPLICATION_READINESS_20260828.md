# Startup Tunisia Application Readiness Pack — 2026-08-28

## Purpose and authority

This pack prepares **Processual Maestro** for Startup Tunisia Label / Pre-Label presentation and evidence packaging. It is an application-readiness document, not a production-launch authorization.

Technical statements in this document must be backed by exact Git SHA + CI/workflow evidence. Company, founder, legal, market-size, customer and financial facts are deliberately left for founder-supplied evidence and must not be inferred from source code.

## Product statement

**Processual Maestro is an adaptive governance, control and evidence layer for AI-agent workflows.** It sits above heterogeneous agent/model runtimes and adds governed access, policy enforcement, CGT evaluation, repair/block/allow decisions, audit evidence, operational limits, entitlement/quota control and admin visibility.

## Problem

AI agents can execute increasingly complex work, but organizations still struggle to prove that execution is bounded, governed, auditable, recoverable and commercially controllable across different runtimes and model providers. Orchestration alone does not provide a portable authority layer for policy, evidence, usage rights and recovery.

## Solution

Processual Maestro provides a runtime-independent control plane that connects:

- governed identity and API access;
- adaptive CGT governance and policy decisions;
- safety guardrails and controlled repair;
- durable audit/evidence trails;
- provider failure containment;
- subscription, entitlement and quota authority;
- commercial/payment qualification without bypassing server-side eligibility;
- administrator/supervisor visibility;
- a sanitized public runtime while proprietary/private CGT capabilities remain protected.

## Innovation thesis

The product is not positioned as another agent framework. Its differentiated thesis is the combination of:

1. **runtime/provider-independent governance** around agent execution;
2. **CGT-based adaptive evaluation** of execution state and transitions;
3. **evidence-producing decisions** rather than opaque allow/deny behavior;
4. **commercial authority connected to runtime rights**, including entitlement and quota consumption;
5. **failure containment and resumable operational flows**;
6. **public/private IP separation** that permits external POC review without disclosing protected implementation.

Every innovation claim used in the application should be demonstrated through a visible workflow or evidence output rather than presented as a generic AI claim.

## Scalability thesis

The architecture supports scale in four dimensions:

- **Technical:** API middleware, PostgreSQL/Redis authority, multi-worker topology, bounded fanout/concurrency, container deployment and provider isolation.
- **Product:** one governance core can supervise different agents, workflows and model providers instead of rebuilding governance for every vertical application.
- **Commercial:** plan, subscription, entitlement and quota contracts make usage rights measurable and enforceable.
- **Deployment:** public evaluation, private engine integration and cloud/container deployment allow multiple operating models.

Market size, customer counts, revenue forecasts and growth assumptions remain founder/business evidence and are not asserted in this technical pack.

## Release authority used for this pack

The application pack follows the clean pre-launch reconciliation chain rather than the divergent historical qualification branch.

Current sequence:

```text
main
  -> PR #184 Release Authority Reconciliation
  -> PR #185 R3 Local Payment Readiness
  -> PR #186 R4 Tunisia Local Top-up Freshness
  -> PR #187 R5 Unified Tunisia Top-up E2E
  -> PR #188 R6 Operational PostgreSQL Evidence
  -> R7 Startup Tunisia Pack
```

Historical PR #165 and historical migrations 0047–0060 must not be merged wholesale for the purpose of this application.

## Exact technical evidence status

### R1 — PostgreSQL resilience

Qualified before the current reconciliation chain. Includes pool pre-ping, timeout/recycle policy, production contracts and regressions.

### R2 — provider failure containment

Qualified before the current reconciliation chain. Includes bounded retries, operation timeout, heartbeat/lease-loss handling, cancellation and cleanup.

### PR #184 — release authority reconciliation

Head recorded in the transition authority: `1e4b871b342a21042f90c78be3c7675301c77103`.

Its exact head passed Public CI, Security Hardening, Orchestration Soak and Topology Benchmark. It also establishes the reconciled production environment and migration authority rather than importing the historical branch wholesale.

### PR #185 — R3 local subscription-payment readiness

Head: `bdb8437d8ae4ac6273628842f6fba55d42daa2d3`.

R3 is qualified. The administrator configures the Tunisia payment destination and uses one **Activate payment route** action; customer visibility remains server-authoritative and fail-closed.

### PR #186 — R4 Tunisia local top-up freshness

Exact head: `a468230ed9cb3f6d46ae5d96d2161abc4648c63d`.

R4 introduced authoritative FX observation metadata including `source`, `reference`, `observed_at`, expiry/freshness checks and rejection of stale or future-dated observations.

The first Topology Benchmark #47 failed on one `RemoteProtocolError` at the maximum two-worker fanout pressure case. The failure was isolated to transport/performance and was not connected to FX/top-up logic. A single failed-job rerun was started according to release policy and passed the previously failing two-worker fanout step. Final run completion must still be recorded before changing the R4 label from **qualification pending final exact-head completion** to **Qualified / Fail-Closed**.

### PR #187 — R5 unified Tunisia top-up E2E

Branch: `agent/prelaunch-r5-tunisia-top-up-e2e`.

Current head at pack creation: `7082565508537e0c54312c09620cc06ed3e56edb`.

A unified regression now proves one coherent flow:

```text
local top-up order
  -> authoritative FX snapshot
  -> TND payment evidence verification
  -> quota grant
  -> identical payment replay without double grant
  -> reversal
  -> identical reversal replay
```

Additional fail-closed coverage includes amount mismatch and rejection of a second distinct reversal decision.

The unified E2E test was added permanently to **Security Hardening**. On the exact R5 head, M1 Runtime Authority Qualification, Security Hardening and Orchestration Soak have already completed successfully at the time this pack was written; Public CI and Topology must be recorded when complete.

### PR #188 — R6 production-like PostgreSQL operational evidence

Branch: `agent/prelaunch-r6-operational-evidence`.

Current head at pack creation: `106cfe69d470665d47e025aca2dd5be8a7fa94a9`.

A dedicated CI rehearsal was added to execute against a real PostgreSQL 17 service:

```text
alembic upgrade head
  -> pg_dump
  -> SHA-256 evidence
  -> restore into isolated database
  -> restored Alembic authority check
  -> upgrade-to-head idempotence
  -> release-contract regression
  -> evidence artifact upload
```

The first workflow attempt exposed an incomplete CI dependency set (`fastapi` missing before migration execution); the workflow was corrected to install application API + database dependencies. The corrected run must complete successfully before R6 is considered qualified.

This rehearsal is intentionally **not** described as a backup of real production data. Real production `MIGRATION_BACKUP_REFERENCE` and `MIGRATION_RESTORE_REHEARSAL_REFERENCE` must only be populated from an actual environment-specific backup/restore operation.

## Readiness classes for the Startup Tunisia presentation

### Demo Ready

The application may demonstrate:

- governed public access and API surface;
- user/organization context;
- plan/entitlement/quota context;
- representative AI-agent execution;
- CGT governance decisions and evidence;
- allowed / blocked / repaired behavior;
- quota/usage consumption;
- administrator/supervisor visibility;
- public/private architecture boundary;
- Tunisia subscription-payment destination setup as a commercial-readiness example.

### Qualified but Fail-Closed

Features may be technically qualified while intentionally disabled for real-money/production use. Tunisia local top-up belongs in this class until all operational evidence, FX authority, payment-evidence policy and production activation checks are closed.

### Production Live

No feature should be called Production Live solely because CI passed. Live status requires environment-specific deployment, secrets, backup/restore references, final release authority and an explicit GO decision.

## Recommended POC story

Use one coherent story rather than a tour of many pages:

```text
User / organization
  -> governed access
  -> plan / entitlement
  -> AI-agent task
  -> CGT governance
  -> allow / block / repair decision
  -> audit evidence
  -> quota consumption
  -> admin/supervisor visibility
```

Close the demo with the Tunisia payment-destination readiness as proof that the governance/runtime core is connected to a real commercial operating model. Do not process real money merely to prove the POC.

## Recommended 12-slide pitch structure

1. Processual Maestro in one sentence.
2. The problem: uncontrolled and non-auditable agent execution.
3. Why now: accelerating AI-agent adoption creates governance demand.
4. Solution: governance/control/evidence layer above agent runtimes.
5. Live POC: one governed end-to-end workflow.
6. Innovation: CGT, adaptive decisions, evidence and runtime-independent authority.
7. Target users and first commercial segment.
8. Business model: subscription/usage rights and enterprise/private deployment options.
9. Scalability: multi-provider, multi-runtime, distributed control plane.
10. Technical proof: CI/security/topology/PostgreSQL/public-private evidence.
11. Team and execution capability — founder-supplied facts only.
12. Roadmap and ask: pilots, Label/Pre-Label objective, market validation and next milestones.

## Three-minute founder-video outline

- **0:00–0:25:** customer problem and target user.
- **0:25–0:55:** what Processual Maestro is.
- **0:55–1:35:** differentiation and innovation.
- **1:35–2:05:** live POC / technical evidence.
- **2:05–2:35:** scalability and business model.
- **2:35–3:00:** founder/team, Tunisia/global ambition and immediate milestone.

The final portal requirement must be rechecked from the official Startup Tunisia site at filing time before recording the video.

## Evidence bundle to assemble

### Technical

- final public release SHA and exact successful workflow/run IDs;
- architecture diagram showing public/private authority boundary;
- controlled live-demo script and demo-account/data policy;
- OpenAPI/API evidence where useful;
- CI, security, soak and topology evidence;
- PostgreSQL backup/restore rehearsal artifact from R6;
- Docker/cloud deployment architecture;
- entitlement/quota and audit evidence;
- public/private compatibility mapping;
- explicit list of fail-closed features.

### Business — founder supplied

- first target customer segment;
- customer problem evidence / interviews / pilots if available;
- competitor/alternative matrix;
- cited market sizing;
- pricing and business-model assumptions;
- 12–18 month milestones;
- financing/resource plan if requested.

### Team — founder supplied

- founder identity and role;
- relevant experience;
- team members and responsibilities;
- hiring plan if relevant.

### Legal/company — founder supplied

- actual incorporation/registry evidence if incorporated;
- shareholder/capital evidence;
- employee/size evidence;
- financial statements where applicable;
- CNSS or other portal-requested evidence where applicable;
- declarations and attachments required by the active Startup Tunisia application session.

## Items that remain outside the technical POC but before commercial production launch

- complete the exact R4 Topology rerun and record evidence;
- complete R5 Public CI and Topology evidence;
- complete corrected R6 PostgreSQL rehearsal and retain its artifact;
- perform an actual environment-specific production backup and restore rehearsal;
- provision final production secrets through the chosen secrets authority;
- execute production-like deployment smoke including restart, health/readiness, login, MFA, admin, subscription, quota, evaluation/API key, audit/outbox and recovery;
- obtain hosted private CI evidence when the account/runner infrastructure allows jobs to start;
- finalize release/branch governance and exact release SHA;
- define operational FX authority and immutable payment-evidence policy before real Tunisia top-up money flows;
- complete accounting/legal/tax/payment review before accepting real funds;
- provision Lemon Squeezy live configuration only when that commercial channel returns to scope.

## Current application-readiness judgment

- **Technical POC:** READY.
- **Innovation evidence:** READY FOR PACKAGING.
- **Scalability architecture:** READY FOR PACKAGING.
- **Unified Tunisia commercial-flow evidence:** IN FINAL QUALIFICATION.
- **Production-like PostgreSQL rehearsal:** IN FINAL QUALIFICATION.
- **Legal/company criteria:** FOUNDER-SUPPLIED / NOT INFERRED.
- **Business/market evidence:** REQUIRES FOUNDER INPUT AND CITED RESEARCH.
- **Startup Tunisia dossier:** TECHNICAL CORE READY; final portal-specific packaging follows after the exact-head technical gates close.
- **Commercial Production Launch:** NOT AUTHORIZED BY THIS DOCUMENT.

## Filing rule

Immediately before submission, re-check the active official Startup Tunisia portal and guidance. Treat the portal itself as the authority for the current session's fields, accepted formats, required legal documents, fees, deadlines, pitch/video constraints and Label vs Pre-Label route.
