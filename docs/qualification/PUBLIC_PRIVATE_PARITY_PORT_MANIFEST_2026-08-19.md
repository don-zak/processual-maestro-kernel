# Public / Private Controlled Boundary Reconciliation Manifest — 2026-08-19

> Historical filename retained for traceability. This document supersedes any earlier interpretation of "parity port" as repository mirroring.

**Public repository:** `don-zak/processual-maestro-kernel`  
**Private repository:** `don-zak/processual-maestro-kernel-private`  
**Private boundary qualification PR:** Draft PR #49 on `agent/private-public-trust-boundary-r1`  
**Status:** **CONTROLLED RECONCILIATION IN PROGRESS — NO WHOLE-REPOSITORY PARITY TARGET**

## 1. Governing architecture

The two repositories are separate trust domains, not two editions that must become source-identical.

- **Public:** governance, orchestration, product contracts, authentication/commercial authority, persistence, qualification, public-safe formal core, sanitized boundary interfaces.
- **Private:** proprietary mathematical execution, equations, weights, thresholds, calibration, private vectors/intermediate state, and private provider implementations.
- **Boundary:** one-way controlled invocation using bounded opaque references, followed by a strictly sanitized decision result.

The approved public decision surface is limited to:

- `existence_rank`
- `dominant_constraint`
- `next_gate`
- `confidence_band`
- `explanation_code`
- `policy_version`

No repository reconciliation task may weaken this boundary.

## 2. Mandatory classifications

Every cross-repository difference must be classified before any port:

### `SHARED_PUBLIC_SAFE`

Code/data that is non-proprietary, belongs to the common product contract, and may intentionally converge after focused tests.

### `PRIVATE_PRESERVE`

Private mathematical/provider implementation that must remain private and must never enter public source, package, image, logs, evidence, exceptions, or telemetry.

Mandatory examples:

- `cgtlib/private/`
- `processual_api/private_integrations/`
- proprietary equations, weights, thresholds and calibration
- private vectors and intermediate mathematical state

### `BOUNDARY_ADAPTER`

Code that mediates between public governance and private execution. It must expose only opaque references on input and sanitized decisions on output, fail closed, and avoid private implementation discovery from the public artifact.

### `ARCHITECTURAL_VIOLATION`

Any path that mixes public governance with private implementation details, performs protected math as an implicit public fallback, imports private source from the public runtime, or exposes private intermediate values. It must be separated before reconciliation can close.

## 3. Non-negotiable source and runtime invariants

1. Public code must not import or discover `cgtlib.private` or `processual_api.private_integrations`.
2. Public wheels/images must not contain those paths.
3. Public runtime must remain importable/buildable/testable without private modules.
4. Protected operations fail closed when no private provider is available; no public substitute equation is permitted.
5. Private provider exceptions must be reduced to generic public errors before crossing the boundary.
6. Public API responses, logs, traces, metrics and qualification evidence must not expose private equations, weights, thresholds, calibration, vectors or intermediate values.
7. Private implementation remains intentionally different; that difference is not automatically a parity defect.
8. No second billing/auth/commercial source of truth may be created merely to make the private repository resemble the public repository.
9. No cross-repository whole-tree copy is permitted.
10. No direct mutation of private `main`; private changes require a dedicated branch, tests and review.

## 4. Reconciliation unit R1 — shared kernel

**Classification:** `SHARED_PUBLIC_SAFE`, subject to file-level review.

Modernization that is demonstrably non-proprietary may converge. A unit must be reclassified if it gains any dependency on private mathematical state or provider implementation.

Source record:

`docs/qualification/PUBLIC_PRIVATE_KERNEL_RECONCILIATION_UNIT_2026-08-19.md`

Required validation:

- focused kernel/adaptive/security tests;
- no private imports;
- public-safe behavior remains standalone.

## 5. Reconciliation unit R2 — `cgtlib`

The package is no longer treated as a single parity unit.

### Shared/public-safe portion

Examples include canonical non-secret data/resources and dependency-light public API declarations where semantic review confirms they contain no proprietary implementation.

### Private-preserve portion

`cgtlib/private/` remains an independent proprietary execution boundary.

### Boundary correction already applied on the public qualification branch

Public modules that directly imported `cgtlib.private` were identified as architectural violations and changed to use public fail-closed surfaces. The public package now declares `_HAS_PRIVATE=False` and does not discover private engine modules.

Required validation:

- public import succeeds with private modules absent;
- protected public mathematical calls fail closed rather than reimplementing private math;
- public wheel excludes private paths;
- canonical shared reference data remains packaged.

## 6. Reconciliation unit R3 — database and migrations

**Classification:** generally `SHARED_PUBLIC_SAFE` for public product persistence, but not automatically a private-runtime requirement.

Public auth/commercial/Admin Marketplace persistence remains public authority. Private mathematical execution should consume only the boundary contract it needs; it does not require a mirrored copy of every public persistence module unless a separately reviewed deployment requirement proves that need.

One coherent migration authority must exist for any deployment that actually hosts public product persistence.

## 7. Reconciliation unit R4 — authentication

Authentication is a public governance/security authority, not private mathematics.

Direction:

- public auth remains canonical product authority;
- private execution must not maintain a competing legacy authentication authority merely for parity;
- private deployments may integrate with authenticated public requests through sanitized identity/context references where required;
- do not copy public auth wholesale into private unless the deployment topology explicitly requires co-location and the copy is classified `SHARED_PUBLIC_SAFE`.

## 8. Reconciliation unit R5 — Admin Marketplace, billing, quotas and pricing

These remain public commercial/governance authorities.

Direction:

- no second private billing/commercial source of truth;
- private math may receive only the minimum governed entitlement/context references required for a protected operation;
- private execution does not gain authority to price, bill, approve quota, or mutate commercial state merely because it participates in evaluation.

## 9. Reconciliation unit R6 — integration control plane

Public integration control remains public-side governance.

Required boundary pattern:

```text
public admission/governance
        |
        | bounded opaque request references
        v
sanitized boundary contract
        |
        | private-side provider composition only
        v
private mathematical execution
        |
        | six-field sanitized decision
        v
public policy/orchestration
```

The private repository may know its own provider modules. The public repository must not import, discover or introspect them.

Existing private `processual_api/integrations/cgt_adapter.py` remains a private-side boundary pattern and is protected by Draft PR #49 tests.

## 10. Reconciliation unit R7 — application composition

The earlier strategy "start `main.py` from public and reinsert private routers" is **superseded**.

Preferred composition:

- public application remains independently runnable and contains no source-level private imports;
- private execution is composed behind the sanitized provider boundary;
- if a same-process private deployment is ever required, that composition belongs only to the private deployment repository and must not cause private discovery code to enter the public artifact;
- public functionality must fail closed when the protected provider is unavailable.

## 11. Reconciliation unit R8 — tests and packaging

Mandatory public gates:

- source scan for forbidden private paths/imports;
- exact sanitized result-schema test;
- provider-exception redaction test;
- public `cgtlib` import without private engine;
- protected math fail-closed regression;
- installed-wheel proof that private paths cannot be imported;
- public governor proof that legacy local-math execution is fail-closed and sanitized decisions drive policy only.

Mandatory private gates:

- private adapter result remains six-field sanitized;
- no proprietary result vectors/weights/thresholds/equations/calibration are exposed by the adapter;
- unavailable/disabled provider errors remain generic;
- private full regression and public-strip/public-boundary suites pass.

## 12. Reconciliation unit R9 — CI, images and evidence

Public CI/evidence may prove only public artifact properties. It must never extract private source or include private implementation in artifacts for convenience.

Private image/build qualification must run in a controlled private context. Public evidence may retain only approved digests/status assertions that do not reveal implementation details.

Container/image SBOM qualification remains separate from the Python-environment SBOM and is not waived.

## 13. Current implementation evidence

Public qualification work now includes:

- neutral `private_evaluation_boundary` contract;
- exact sanitized decision regression tests;
- public source private-import exclusion tests;
- public protected-math fail-closed wrappers;
- explicit `_HAS_PRIVATE=False` public package behavior;
- Packaging Qualification wheel-level exclusion and smoke checks;
- sanitized public governor path with legacy local-math `govern_answer` disabled fail-closed.

Private Draft PR #49 adds adapter-boundary tests on a dedicated private branch. It does not change private mathematical implementation or grant runtime authority.

## 14. Explicitly prohibited shortcuts

Rejected:

- whole-tree public → private copying;
- private → public source copying;
- importing private modules conditionally from public code;
- preserving a public mathematical fallback that duplicates protected private execution;
- exposing raw vectors/scores merely because older API/tests did so;
- treating absence of private implementation from public as a parity defect;
- merging private Draft PR #49 as part of this manifest without independent review;
- declaring staging or production readiness from repository tests alone.

## 15. Exit criteria

Repository boundary reconciliation closes only when:

- all inspected differences are deliberately classified;
- all `ARCHITECTURAL_VIOLATION` paths in the runtime boundary are removed or isolated;
- public source/package/image exclusion proofs pass;
- private adapter boundary tests pass;
- public governance consumes only sanitized decisions for protected evaluation;
- no duplicate auth/billing/commercial authority is introduced;
- required shared/public-safe drift is intentionally reconciled;
- build/test evidence is retained with exact source identities;
- reviewers confirm the trust boundary without granting real-environment authority.

Until then:

`RepositoryReconciliationComplete=false`

`PrivateRuntimeAuthorityGranted=false`

`RealStagingQualified=false`

`ProductionAuthorityGranted=false`
