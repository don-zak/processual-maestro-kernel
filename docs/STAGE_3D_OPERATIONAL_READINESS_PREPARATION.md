# Stage 3D — Operational Readiness Preparation

Stage 3D prepares the repository for real staging while external GCP billing remains unavailable. It is deliberately non-authoritative for real staging and production.

## Scope

The stage verifies that the repository already exposes the static/runtime surfaces required for the later real-staging proof:

- liveness, readiness, and Prometheus metrics endpoints;
- request ID, metrics, and audit middleware registration;
- browser-facing public and administrator routes needed for real browser E2E;
- production documentation disablement;
- wildcard CORS rejection and weak-secret fail-closed policy;
- Docker runtime exclusion markers for private implementation directories;
- declared load/endurance targets for later real staging execution.

## Run

```powershell
.\scripts\Test-PMKStage3DOperationalReadiness.ps1
```

The generated local evidence is:

`.pmk-validation/stage3d-operational-readiness.json`

The validator never records secret values and never sets real staging or production authority.

## Authority boundary

A local/static PASS means only that the repository is prepared for the later real-staging tests. It does not prove alert delivery, external-provider connectivity, real browser E2E, load/endurance capacity, or a human security review.

Those gates remain explicitly required on the real staging environment before `RealStagingQualified` can become true.
