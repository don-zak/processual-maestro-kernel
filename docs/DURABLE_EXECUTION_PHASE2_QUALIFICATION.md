# Durable Execution — Phase 2 Qualification Matrix

Status date: 2026-08-08
Branch: `feat/a3-admin-marketplace-original-offers`
Scope: scale, adaptive capacity, resilience, and production qualification for durable execution.

## Purpose

This document consolidates the completed Phase 2 durable-execution work so the subsystem can be reviewed as one coherent unit and the broader program review can move to another area without losing qualification context.

The implementation remains intentionally opt-in. This document does **not** authorize changing production worker defaults, enabling optimized Redis globally, wiring durable execution into `main.py`, or enabling adaptive concurrency by default.

## Invariants preserved

- Production worker-count default remains unchanged.
- `main.py` remains unchanged by this qualification work.
- Optimized Redis durable storage remains opt-in.
- Adaptive concurrency remains opt-in.
- Production pool defaults remain `idle_poll_seconds=0.05` and `recovery_interval_seconds=1.0`.
- Faster polling values are used only in tests/benchmarks.
- Base CI qualification remains 1/2/4/8 workers. 16 workers is not part of the base gate.
- No generic/global Redis lock is introduced.
- No queue scan is added to the hot claim path.
- Capacity remains fail-closed.
- Durable `RUNNING` means claimed/leased; it must not be interpreted as domain-capacity-admitted handler activity.

## Phase 2 qualification matrix

| Area | Qualification | Status | Evidence |
|---|---|---|---|
| Durable state machine | submit/claim/heartbeat/succeed/fail/cancel/recovery | PASS | durable execution contract tests |
| Redis durability | shared state across store instances | PASS | Redis durable execution tests |
| Idempotency | concurrent duplicate submit creates one durable job | PASS | concurrent Redis submit tests |
| Duplicate execution | duplicate submissions execute once across multi-worker pool | PASS | `test_duplicate_submissions_execute_once_across_worker_pool` |
| Lease ownership | two workers cannot claim the same job | PASS | Redis claim contract tests |
| Stale ownership | old worker cannot complete after lease recovery | PASS | stale-owner Redis test |
| Node loss / resume | cancelled worker leaves durable lease; replacement node recovers and completes | PASS | `test_cancelled_worker_is_recovered_by_replacement_node` |
| Retry continuity | retry survives store/worker instance changes | PASS | Redis retry continuity test |
| Deadline safety | queued and running deadline expiry remains fail-closed | PASS | Redis deadline tests |
| Shared capacity | domain/global capacity shared across controllers/workers | PASS | Redis domain-capacity tests |
| Cross-node quota | independent controllers enforce the same Redis-backed limits | PASS | shared-capacity qualification |
| Emergency reserve | normal work cannot consume reserved emergency capacity | PASS | capacity policy tests |
| Noisy neighbor | batch saturation does not starve NOC emergency work | PASS | real Redis 8-worker qualification |
| Capacity attempts | saturated claim is requeued without burning an execution attempt | PASS | two-worker capacity test |
| Capacity lease recovery | expired Redis capacity leases self-recover | PASS | capacity recovery test |
| Adaptive controller | AIMD, EWMA, hysteresis, floor/ceiling | PASS | adaptive controller tests |
| Hard provider pressure | timeout/429 causes immediate multiplicative decrease | PASS | adaptive controller/gate tests |
| Slow provider | sustained latency pressure requires hysteresis before decrease | PASS | adaptive gate tests |
| Recovery | healthy windows restore concurrency gradually | PASS | adaptive controller/gate tests |
| Active-work safety | decreasing the limit does not cancel active work | PASS | adaptive gate test |
| Wake-up behavior | increasing limit wakes blocked workers without polling | PASS | adaptive gate test |
| Automatic telemetry | completed executions automatically produce control samples | PASS | sampler + pool feedback tests |
| 429 classification | provider-specific classifier can mark rate-limited attempts | PASS | telemetry sampler tests |
| Timeout classification | default classifier recognizes `TimeoutError` conservatively | PASS | telemetry sampler tests |
| Infra/provider isolation | claim/Redis infrastructure errors do not feed provider pressure | PASS | `test_infrastructure_failure_does_not_feed_provider_pressure` |
| Redis atomic claim path | optimized hash-tagged deployment uses Lua/EVAL | PASS | optimized Redis tests + benchmark telemetry |
| Scale baseline | 1/2/4/8 worker benchmark completes all jobs with zero true errors | PASS | Durable Execution CI benchmark |
| CI contract gate | Ruff + durable contracts + Redis qualification | PASS | Durable Execution workflow |

## Latest CI qualification snapshot

Durable Execution workflow run #69 completed the expanded resilience suite successfully:

- Ruff: PASS
- Durable execution tests: **109 passed**
- Benchmark: 1/2/4/8 workers, 96 jobs per trial, 3 repetitions
- True errors: **0 at every worker count**

Median benchmark snapshot from that run:

| Workers | Successful workflows/s | Execution p95 | Queue p95 |
|---:|---:|---:|---:|
| 1 | 41.58/s | 20.91 ms | 2187.09 ms |
| 2 | 75.75/s | 20.92 ms | 1172.42 ms |
| 4 | 140.69/s | 20.94 ms | 615.06 ms |
| 8 | 221.79/s | 21.33 ms | 368.64 ms |

These numbers are a CI-run snapshot, not a production capacity promise. Hosted-runner variance is expected; qualification depends on correctness, zero true errors, latency behavior, and repeated scaling evidence rather than one throughput number.

## What is now closed at code/CI qualification level

The following Phase 2 engineering concerns are now covered sufficiently to move the code-review focus elsewhere:

1. Durable Redis execution semantics and ownership.
2. Multi-worker and multi-controller correctness.
3. Idempotency and duplicate-submit protection.
4. Lease recovery after worker/node interruption.
5. Shared domain/global capacity and emergency reserve.
6. Real-Redis noisy-neighbor/NOC-reserve behavior.
7. Optimized atomic Redis claim path under the opt-in store.
8. Adaptive concurrency decision logic.
9. Opt-in dynamic concurrency gating.
10. Automatic latency/error telemetry feedback.
11. Separation of infrastructure failures from provider-pressure feedback.
12. Stable 1/2/4/8 worker CI qualification.

## Operational qualification still required before changing production defaults

The items below are deliberately **not** treated as reasons to keep modifying the core implementation. They are deployment/staging qualification gates and should be executed in the target environment before any production-default change:

- Repeated qualification runs on production-like infrastructure.
- Noisy-neighbor tests with realistic traffic distributions and payload sizes.
- NOC/emergency reserve validation with real operational traffic classes.
- Slow-provider and real 429/timeout injection against provider adapters.
- Redis degradation/failover testing using the actual deployment topology.
- Process/node termination and restart under orchestration.
- Extended soak with representative job mix and payload sizes.
- Cross-node quota validation under the deployed Redis topology.
- Canary/staging observation before any production-default activation.

These are environment-level acceptance exercises, not justification for speculative core rewrites.

## Activation rule

Do not change production defaults merely because this matrix is green. Activation should occur only after the operational qualification above is completed and reviewed. Until then:

- keep optimized Redis explicit,
- keep adaptive concurrency explicit,
- keep current worker defaults,
- keep durable execution startup explicit,
- preserve existing fail-closed behavior.

## Review handoff

For subsequent program review, durable execution can now be treated as a consolidated Phase 2 subsystem with green code/CI qualification. Return to this area only for:

- a reproducible correctness regression,
- an operational qualification failure,
- a measured bottleneck with evidence,
- or an explicit decision to begin staged production activation.
