# Startup Tunisia Application Readiness — Processual Maestro

**Reference date:** 2026-08-28  
**Technical release authority:** `cd93a0ce97b6db886c000a747d3981ecb80241c8`  
**Application status:** TECHNICAL POC READY / DOSSIER PACKAGING IN PROGRESS  
**Commercial production status:** NO-GO until environment-specific launch evidence is closed.

## 1. Product statement

**Processual Maestro is an adaptive governance, control and evidence layer for AI-agent workflows.** It sits above heterogeneous agent/model runtimes and adds governed access, policy enforcement, CGT evaluation, controlled allow/block/repair decisions, audit evidence, operational limits, entitlement/quota authority and administrator visibility.

## 2. Problem

Organizations can increasingly automate work with AI agents, but agent orchestration alone does not prove that execution is bounded, governed, auditable, recoverable or commercially controllable across providers and runtimes.

Key gaps addressed by Processual Maestro:

- portable governance above different agent/model runtimes;
- enforceable policy and safety decisions;
- auditable execution evidence;
- bounded capacity and provider-failure containment;
- usage rights linked to subscriptions, entitlements and quotas;
- operational recovery and replay/idempotency guarantees;
- safe external evaluation without disclosing the private engine.

## 3. Solution

Processual Maestro provides a runtime-independent control plane connecting:

```text
Identity / governed access
  -> Plan / entitlement / quota authority
  -> AI-agent task
  -> CGT governance
  -> allow / block / repair
  -> execution + provider containment
  -> audit evidence
  -> quota consumption
  -> admin / supervisor visibility
```

Commercial qualification is attached to the same authority model rather than implemented as an unrelated payment shortcut.

## 4. Mapping to Startup Tunisia innovation criterion

The innovation case should be demonstrated, not asserted. The strongest differentiators are:

1. **Runtime/provider-independent governance** around agent execution rather than another agent framework.
2. **CGT-based adaptive evaluation** of workflow/execution state.
3. **Evidence-producing decisions** with auditable allow/block/repair outcomes.
4. **Commercial rights connected to runtime authority** through subscriptions, entitlements and quota consumption.
5. **Failure containment and resumable/idempotent operations** instead of fragile one-shot automation.
6. **Public/private IP separation** enabling external POC review without exposing proprietary modules.

## 5. Mapping to Startup Tunisia scalability criterion

### Technical scalability

- API middleware architecture.
- PostgreSQL authoritative persistence.
- Redis distributed capacity/concurrency authority.
- multi-worker topology qualification.
- bounded fanout and provider failure containment.
- container/cloud deployment path.

### Product scalability

One governance core can supervise different agent workflows, model providers and organizational use cases rather than rebuilding governance separately for each vertical.

### Commercial scalability

Plans, subscriptions, entitlements and quotas provide measurable usage rights and support subscription/usage-based commercialization.

### Deployment scalability

A sanitized public runtime supports evaluation, while private/proprietary capabilities remain separated. Production can be container/cloud deployed with organization-owned provider credentials.

> Market size, customer numbers, revenue, traction and team claims are business/founder evidence. They must be supplied from real records and are not inferred from the repository.

## 6. Current clean release chain

```text
main
  -> PR #184 Release Authority Reconciliation
  -> PR #185 R3 Local Payment Readiness
  -> PR #186 R4 Tunisia Local Top-up Freshness
  -> PR #187 R5 Unified Tunisia Top-up E2E
  -> PR #188 R6 Operational PostgreSQL Evidence
  -> R7 Startup Tunisia Pack
```

Do not merge historical PR #165 or historical migrations 0047–0060 wholesale for application packaging.

## 7. Exact technical evidence

### R1 — PostgreSQL resilience

Qualified hardening includes pool pre-ping, connection timeout/recycle policy, production settings contracts and regression coverage.

### R2 — provider failure containment

Qualified hardening includes bounded retries, operation timeout, heartbeat/lease-loss handling, cancellation and cleanup.

### PR #184 — Release Authority Reconciliation

Head: `1e4b871b342a21042f90c78be3c7675301c77103`.

The recorded exact head passed Public CI, Security Hardening, Orchestration Soak and Topology Benchmark and established the clean release/migration authority.

### PR #185 — R3 Tunisia subscription-payment readiness

Head: `bdb8437d8ae4ac6273628842f6fba55d42daa2d3`.

R3 is qualified. The administrator configures the payment destination and uses one **Activate payment route** action; customer visibility remains server-authoritative and fail-closed.

### PR #186 — R4 Tunisia local top-up freshness

Head: `a468230ed9cb3f6d46ae5d96d2161abc4648c63d`.

R4 added authoritative FX observation metadata and freshness validation: `source`, `reference`, `observed_at`, expiry, stale/future rejection.

The original R4 Topology run history must remain transparent: the initial run failed once at maximum two-worker fanout due to a transport error; its single allowed rerun passed that point but later failed one staging-canary sample. No Tunisia/FX code was changed to hide the variance. The downstream R5 exact head, which contains R4 plus only E2E/security-test additions, passed the full Topology Benchmark including staging canary. Therefore the qualified release evidence is carried by the downstream exact head rather than rewriting the historical R4 result.

### PR #187 — R5 unified Tunisia top-up E2E

Exact head: `7082565508537e0c54312c09620cc06ed3e56edb`.

Exact-head gates:

- Public CI — SUCCESS.
- Security Hardening — SUCCESS.
- M1 Runtime Authority Qualification — SUCCESS.
- Orchestration Soak — SUCCESS.
- Topology Benchmark — SUCCESS, including staging canary.
- Public-repository Private CI — SKIPPED as designed.

Unified E2E now proves:

```text
local top-up order
  -> authoritative FX snapshot
  -> TND payment evidence verification
  -> atomic quota grant
  -> identical payment replay without double grant
  -> reversal
  -> identical reversal replay
```

Fail-closed coverage also includes payment amount mismatch and rejection of a second distinct reversal decision.

### PR #188 — R6 PostgreSQL operational evidence

Exact head: `cd93a0ce97b6db886c000a747d3981ecb80241c8`.

Operational evidence run: `33166590476` — **SUCCESS**.

It executed on PostgreSQL 17:

```text
migration contract regression
  -> full Alembic upgrade from blank DB to 20260828_0047r
  -> PostgreSQL 17 pg_dump
  -> SHA-256 dump evidence
  -> restore into isolated DB
  -> restored Alembic authority check
  -> upgrade-to-head idempotence
  -> release environment contract tests
  -> evidence artifact upload
```

The rehearsal exposed and fixed a real PostgreSQL migration defect in `20260807_0039_top_up_quota_grants.py`: JSON comparisons/assignment were made PostgreSQL-safe and a permanent regression contract was added.

Evidence:

- DB dump SHA-256: `dfbf4c3ac2f52aadbebddf3d04b75a33db3c768baa29445e7e982e8a16b5784b`.
- Artifact ID: `9683836066`.
- Artifact name: `prelaunch-postgres-backup-restore-evidence`.
- Artifact ZIP digest: `sha256:bdbf4bab39c92736a5da45bfdcd26deb6d77e432a84582be543bcefbbd8dcd69`.
- Restored Alembic revision: `20260828_0047r`.
- Production environment release contract: `3 passed`.

This is a production-like automated rehearsal, **not** a backup of real production data. Live `MIGRATION_BACKUP_REFERENCE` and `MIGRATION_RESTORE_REHEARSAL_REFERENCE` must only be populated from the actual target environment.

At pack creation, R6 exact-head Security Hardening, M1 and Pre-launch Operational Evidence are successful; Public CI, Soak and Topology are still completing and must be recorded before calling R6 fully qualified.

## 8. Readiness classes for presentation

### Demo Ready

Safe to demonstrate:

- governed public access/API surface;
- user/organization context;
- plan/entitlement/quota context;
- representative AI-agent execution;
- CGT governance decisions;
- allowed / blocked / repaired behavior;
- audit evidence;
- quota consumption;
- admin/supervisor visibility;
- public/private architecture boundary;
- Tunisia subscription-payment destination setup as commercial-readiness evidence.

### Qualified but Fail-Closed

Tunisia local top-up is technically advanced and covered by E2E/operational evidence but remains intentionally fail-closed for real money until operational FX authority, immutable payment-evidence policy and final environment gates are closed.

### Production Live

No capability is called Production Live solely because CI passed. Live status requires target-environment secrets/configuration, real backup/restore references, deployment smoke, final release authority and an explicit GO decision.

## 9. Recommended POC story

Use one coherent story rather than a tour of many screens:

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

Close with Tunisia payment-destination readiness as proof that the governance/runtime layer connects to a real commercial operating model. Do not process real money simply to demonstrate the POC.

## 10. Current application judgment

- **Technical POC:** READY.
- **Innovation evidence:** READY FOR PRESENTATION.
- **Scalability architecture:** READY FOR PRESENTATION.
- **Unified Tunisia commercial-flow evidence:** QUALIFIED on R5 exact head.
- **Automated PostgreSQL migration/backup/restore rehearsal:** QUALIFIED on R6 exact head/run.
- **Business/market evidence:** REQUIRES FOUNDER-SUPPLIED FACTS + CITED RESEARCH.
- **Legal/company evidence:** REQUIRES ACTUAL COMPANY DOCUMENTS / PORTAL ROUTE.
- **Startup Tunisia dossier:** TECHNICAL CORE READY; portal and presentation assets are prepared in the companion files in this directory.
- **Commercial production launch:** NO-GO until environment-specific blockers are closed.

## 11. Remaining production-only blockers (not Startup Tunisia POC blockers)

- final R6 Public CI/Soak/Topology exact-head completion;
- actual target-environment backup/restore references;
- production secrets provisioning;
- production-like deployment smoke with restart/health/login/MFA/admin/subscription/quota/evaluation/audit/recovery;
- hosted private CI when runner/account infrastructure permits jobs to start;
- final branch/release governance and release SHA;
- operational USD/TND FX authority;
- immutable/auditable payment-evidence operating policy;
- accounting/legal/tax/payment review before accepting real funds;
- Lemon Squeezy live provisioning when that channel returns to scope.

These items must not be presented as completed merely to strengthen a demo or application.