# Durable Execution — Phase 2 Qualification Matrix

Status date: 2026-08-08
Branch: `feat/a3-admin-marketplace-original-offers`
Scope: scale, adaptive capacity, resilience, and production qualification for durable execution.

## Purpose

This document is the authoritative handoff and go/no-go record for the durable-execution Phase 2 work. The implementation remains opt-in; this document does not authorize changing production worker defaults, enabling optimized Redis globally, wiring durable execution into `main.py`, or enabling adaptive concurrency by default.

## Invariants preserved

- Production worker-count default remains unchanged.
- `main.py` remains unchanged by this qualification work.
- Optimized Redis durable storage remains opt-in.
- Adaptive concurrency remains opt-in.
- Production pool defaults remain `idle_poll_seconds=0.05` and `recovery_interval_seconds=1.0`.
- Faster polling values are test/benchmark-only.
- Base CI remains 1/2/4/8 workers; 16 workers is qualification-only and manual.
- No generic/global Redis lock or queue scan is added to the hot claim path.
- Capacity remains fail-closed.
- Durable `RUNNING` means claimed/leased, not necessarily handler-active.

## Code and CI qualification

| Area | Status | Evidence |
|---|---|---|
| Durable state machine and Redis persistence | PASS | durable contract + Redis tests |
| Idempotent submit and duplicate execution | PASS | concurrent submit + multi-worker execution qualification |
| Lease ownership and stale-owner protection | PASS | Redis ownership tests |
| Node loss / resume | PASS | replacement-node recovery qualification |
| Retry and deadline safety | PASS | Redis continuity/deadline tests |
| Shared global/domain quota across workers | PASS | Redis capacity tests |
| Emergency reserve and noisy-neighbor isolation | PASS | 8-worker real-Redis qualification |
| Capacity lease recovery | PASS | Redis capacity recovery test |
| Optimized atomic claim path | PASS | Lua/EVAL tests + telemetry |
| Adaptive AIMD/EWMA/hysteresis | PASS | adaptive controller tests |
| 429/timeout/slow-provider pressure | PASS | adaptive gate + telemetry tests |
| Healthy recovery | PASS | adaptive recovery tests |
| Active-work safety | PASS | limit decrease does not cancel active work |
| Infrastructure/provider isolation | PASS | Redis/claim failure is not provider pressure |
| Base scale qualification | PASS | 1/2/4/8 benchmark, zero true errors |

Latest expanded Durable Execution run #69: Ruff PASS, **109 tests passed**, 1/2/4/8 benchmark PASS, zero true errors.

## Preproduction automation added

`.github/workflows/durable-preproduction-qualification.yml` is a manual production-qualification workflow. It deliberately does not run as base CI. Defaults:

- 8 workers only;
- 384 jobs per trial;
- 5 repetitions;
- Redis telemetry enabled;
- resilience/adaptive/capacity qualification tests rerun before scale measurement.

The optional `include_16_workers` input enables a 16-worker tier only for explicit qualification. Passing 16 workers is evidence for capacity exploration, not permission to change production defaults.

## Existing wider-system qualification

The repository already contains separate workflows for wider runtime behavior:

- `staging-canary.yml`: repeated one-vs-two-worker workload and execution-mix canary with a median gate and uploaded evidence.
- `orchestration-soak.yml`: sustained orchestration mix, widths through 16, multiple concurrency levels, repeated trials, and metrics verification.
- `topology-benchmark.yml`: worker-topology comparisons for application workloads, fanout, execution mix, and staging gate evidence.

Recent recorded staging-canary and orchestration-soak runs were green. They are useful preproduction evidence but run on GitHub-hosted infrastructure; they do not substitute for the target deployment topology.

## Release-chain correction

Preproduction review found stale migration-head assumptions in the release path. They were corrected:

- `.github/workflows/release.yml` now requires Alembic head `20260807_0043` instead of `20260805_0029`.
- `tests/test_migration_regression_lock_a3.py` now asserts `20260807_0043`.
- `tests/test_sqlite_migration_chain.py` now asserts head `20260807_0043` and one-step downgrade to `20260807_0042`.

This prevents a release gate from certifying an obsolete schema head.

## Production activation gate

Production activation is **NO-GO** until every EXTERNAL item below is executed against the actual staging/production-like environment and evidence is reviewed.

| Gate | State before activation | Required evidence |
|---|---|---|
| Code/CI durable contracts | READY | green Durable Execution workflow |
| Repeated 8-worker qualification | READY TO RUN | manual durable-preproduction artifact |
| 16-worker exploration | OPTIONAL | manual artifact; never a default gate |
| Staging canary | READY TO RUN | canary artifacts from target candidate |
| Extended soak | READY TO RUN | sustained workload artifact |
| Redis topology failover/degradation | EXTERNAL | actual managed/self-hosted Redis failover evidence |
| Orchestrator node/process termination | EXTERNAL | target platform termination/restart evidence |
| Cross-node quota on deployed Redis | EXTERNAL | multiple deployed nodes sharing the target Redis topology |
| Provider 429/timeout/slow injection | EXTERNAL | adapter-level fault injection against staging providers/mocks |
| NOC/emergency traffic classes | EXTERNAL | production-like traffic mix evidence |
| Secrets/configuration readiness | EXTERNAL | release gate with real staging secret/config set |
| Database migration on staging clone | EXTERNAL | upgrade to `20260807_0043`, smoke verification, rollback/recovery plan |
| Canary observation | EXTERNAL | agreed observation window with no correctness/SLO regression |

## Go/no-go rules

Do not enable production defaults if any of the following is true:

1. any durable job is lost, duplicated, or completed by a stale owner;
2. cross-node capacity exceeds configured global/domain limits;
3. emergency traffic is starved under realistic noisy-neighbor load;
4. Redis failure is misclassified as provider pressure or leaves unrecoverable state;
5. provider 429/timeouts fail to reduce concurrency or healthy windows fail to recover it;
6. migration head is not exactly `20260807_0043` for this release candidate;
7. release/staging configuration is incomplete or fail-open;
8. target-topology canary or soak shows unresolved correctness, saturation, or SLO regression.

## Activation sequence after all gates are green

1. Deploy the candidate to staging with current production defaults unchanged.
2. Run migration verification and commercial staging smoke.
3. Run durable preproduction 8-worker repeated qualification and archive evidence.
4. Run target-topology Redis degradation, node-loss/resume, cross-node quota, provider-fault, noisy-neighbor, and soak exercises.
5. Run staging canary and review metrics/errors/queue and execution latency together.
6. If all evidence is green, enable optimized Redis only in the intended canary scope.
7. Enable adaptive concurrency only in the intended canary scope with explicit policy bounds.
8. Observe canary before increasing traffic or changing worker defaults.
9. Change defaults only through a separate reviewed production-activation change.

## Current decision

Repository-side preparation is complete enough to execute preproduction qualification. **Production activation itself remains blocked on target-environment evidence and real secrets/topology.** This is intentional fail-closed behavior, not unfinished core development.
