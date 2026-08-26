# Public / Private Reconciliation Trust-Boundary Addendum — 2026-08-19

## Precedence

This addendum constrains and clarifies every public/private reconciliation record created before it. If an earlier statement can be read as requiring source-level parity that would expose or weaken the proprietary mathematical boundary, this addendum takes precedence.

## Correct reconciliation objective

The private repository is **not** a source-identical superset of the public repository.

The correct target is:

- public governance/product/orchestration capabilities remain complete and usable;
- protected mathematics remain isolated in the private repository/runtime;
- only public-safe contracts and adapters may cross the repository/runtime boundary;
- private provider composition remains private;
- public artifacts, logs, APIs, browser surfaces, telemetry and evidence never expose protected private content.

## Mandatory classification

Every candidate change must be classified before porting:

- `SHARED_PUBLIC_SAFE`
- `PRIVATE_PRESERVE`
- `BOUNDARY_ADAPTER`
- `ARCHITECTURAL_VIOLATION`

`ARCHITECTURAL_VIOLATION` blocks the port until the mixed code is split.

## Prohibited reconciliation actions

The following are prohibited:

- repository-wide public → private overwrite;
- private → public copying of mathematical implementation;
- moving equations, weights, thresholds, calibration, raw vectors, intermediate scores, or private datasets into public shared modules;
- making public runtime imports depend on private implementation modules;
- duplicating private mathematics in public as fallback behavior;
- exposing private exception payloads, stack traces, paths or debug representations through public surfaces;
- treating successful private evaluation as authority to reveal private internals.

## Approved composition model

The public side defines a bounded protocol and sanitized decision schema.

The private side composes a provider implementation behind that protocol. The provider resolves private state and mathematics internally, then returns only the approved sanitized decision fields.

Current R1 sanitized decision fields are exactly:

- `existence_rank`
- `dominant_constraint`
- `next_gate`
- `confidence_band`
- `explanation_code`
- `policy_version`

Any schema expansion requires a separate review and updated boundary tests.

## Qualification gates added

Public qualification branch now includes:

- `processual_api/integrations/private_evaluation_boundary.py`
- `tests/test_private_evaluation_boundary.py`
- `tests/test_public_private_source_boundary.py`
- `docs/architecture/PUBLIC_PRIVATE_TRUST_BOUNDARY_R1.md`
- Packaging Qualification coverage for installed-wheel private-module exclusion and public-boundary importability.

Private qualification is isolated on:

- branch `agent/private-public-trust-boundary-r1`
- draft PR #49
- `tests/test_private_public_trust_boundary_r1.py`

## Closure requirement

Repository reconciliation cannot close until both repositories independently pass their trust-boundary qualification and the eventual private parity port preserves these invariants.

Current authority remains fail closed:

`RepositoryReconciliationComplete=false`

`PrivateRuntimeAuthorityGranted=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
