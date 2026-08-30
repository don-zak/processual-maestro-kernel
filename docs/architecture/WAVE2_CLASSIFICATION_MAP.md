# Wave 2 Classification and Contracts Map

This document records the evidence-backed classification baseline produced after Wave 1. It does **not** authorize source relocation by itself.

## Safety baseline

Wave 2 starts from green `main` commit:

`9063833418fcff86ac23fe0891ef960e00a0d67a`

Before this mapping work began, the post-merge Public CI, Security Scan, Security Hardening, and Branch Protection gates were green. No runtime/application source is moved, renamed, split, or deleted in this mapping stage.

## Dependency census evidence

The GitHub Actions dependency census for this branch reports:

| Package | Python files | Python bytes |
| --- | ---: | ---: |
| `processual_kernel` | 53 | 389,136 |
| `cgtlib` | 37 | 93,887 |
| `processual_api` | 397 | 3,381,133 |
| **Total** | **487** | **3,864,156** |

Observed cross-package edges:

| From | To | Files with edge |
| --- | --- | ---: |
| `processual_api` | `cgtlib` | 4 |
| `processual_api` | `processual_kernel` | 8 |
| `processual_kernel` | `cgtlib` | 2 |

No `processual_kernel -> processual_api` or `cgtlib -> processual_api` reverse edge was observed.

## Exact cross-package edge files

### `processual_kernel -> cgtlib`

- `processual_kernel/cgt_bridge.py`
- `processual_kernel/governor.py`

These two files are integration/governance seams, not contract extraction candidates.

### `processual_api -> cgtlib`

- `processual_api/adapters/cgt_adapter.py`
- `processual_api/adapters/frontend_adapter.py`
- `processual_api/routers/cgt.py`
- `processual_api/routers/health.py`

### `processual_api -> processual_kernel`

- `processual_api/adapters/kernel_adapter.py`
- `processual_api/cgt_governor/security/guard.py`
- `processual_api/dependencies.py`
- `processual_api/routers/cgt_governor.py`
- `processual_api/routers/reports.py`
- `processual_api/routers/settings.py`
- `processual_api/routers/telemetry.py`
- `processual_api/routers/workflows.py`

The direction of these edges is consistent with an inward dependency model: transport/adapters depend on kernel/governance, not the reverse.

## Evidence-backed classification

### Contracts

Strong first-class contract candidates:

- `processual_kernel/types.py`
  - stdlib-only imports;
  - owns core enums, immutable/mutable records, workflow/task envelopes, governance decision shapes, and the `AgentRuntime` / `AuditSink` protocols;
  - imported as a foundational type surface by kernel logic.
- `cgtlib/types.py`
  - stdlib-only;
  - owns CGT parameter/state/report shapes and `ExistenceRank`.
- `cgtlib/errors.py`
  - stdlib-only;
  - owns the CGT exception contract.
- `cgtlib/constants.py`
  - no imports; treat as governance contract/configuration surface pending semantic review.

Contracts-adjacent, but **not** first extraction candidates:

- `processual_kernel/adaptive_types.py`
  - predominantly enums/dataclasses, but currently depends on `KernelPolicy` and `MaestroAction` from `processual_kernel/types.py`;
  - should follow the core type boundary rather than lead it.
- `processual_kernel/security/exceptions.py`
- `processual_kernel/security/policies.py`
- `processual_kernel/notifications/types.py`

These may become subdomain contracts later, after import-consumer evidence is reviewed.

### Core / Kernel

Keep in the inward core/runtime domain for now:

- `processual_kernel/kernel.py`
- `processual_kernel/continuity.py`
- most of `processual_kernel/adaptive/**` that implements decision, convergence, checkpoints, safety, policy selection, and execution behavior.

Do not move persistence, encryption, observability, notification delivery, or external SDK integrations into a future core package merely because they currently live under `processual_kernel`.

### Governance / CGT

Primary governance domain:

- `cgtlib/**` other than the small contract surfaces above;
- `processual_kernel/governor.py`;
- `processual_kernel/cgt_bridge.py` as the current kernel-to-governance seam.

The two observed `processual_kernel -> cgtlib` edges are therefore expected integration edges, not reverse-architecture violations.

### Runtime / Orchestration

Runtime candidates include:

- `processual_kernel/kernel.py`;
- adaptive runtime/control components under `processual_kernel/adaptive/**`;
- `processual_api/execution/**` and orchestration-facing services, subject to a second-level import review before any relocation.

### Outward adapters and delivery surfaces

`processual_api` is the present broad umbrella and the main decomposition target. Initial path-level classification:

- HTTP / transport: `processual_api/routers/**`, `processual_api/main.py`, `processual_api/schemas/**`.
- Composition / dependency wiring: `processual_api/dependencies.py`.
- Kernel / CGT adapters: `processual_api/adapters/**`.
- Persistence: `processual_api/db/**` plus SQL-backed units of work and repositories distributed in feature packages.
- Cache: `processual_api/cache/**`.
- Identity / security delivery: `processual_api/auth/**`, middleware, RBAC/session-key surfaces.
- Commercial / marketplace: `processual_api/admin_marketplace/**`, `processual_api/billing/**`.
- Integrations / providers: `processual_api/integrations/**`.
- Governance API/support: `processual_api/cgt_governor/**`.
- Application services: `processual_api/services/**`.

This is a classification map, not yet a physical package plan. Feature packages may contain a mixture of domain, application, persistence, and transport code and therefore require file-level review before movement.

## First safe extraction candidate

The first physical extraction candidate is the semantic surface currently in `processual_kernel/types.py`, but **no move is approved in this PR stage**.

Before extraction, the next gate is:

1. enumerate every importer of `processual_kernel.types` and its exported symbols;
2. separate stable contracts from stateful/internal records if consumers show different responsibilities;
3. define compatibility imports so existing public imports remain valid;
4. add architecture/contract tests before moving any symbol;
5. run the full Public CI + security gates;
6. move the smallest coherent contract slice only after the above stays green.

`cgtlib/types.py` and `cgtlib/errors.py` should remain inside the governance boundary until the kernel contract extraction proves the compatibility pattern safely.

## Explicit non-goals for this stage

- no new repository split;
- no mass namespace rename;
- no deletion/archive decision based only on path names;
- no moving `processual_api` feature packages wholesale;
- no strengthening architecture rules beyond what the measured dependency graph supports;
- no change to runtime behavior, commercial flows, quotas, authority, security, or provider execution.
