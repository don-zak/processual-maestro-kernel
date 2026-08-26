# Stage 3C — Staging Runtime Readiness

Stage 3C prepares the repository and runtime contract for real staging while the external GCP billing gate is unresolved. It is a preparation gate only and never grants production or real-staging authority.

## Goals

- keep all real secret values outside repository authority;
- define the exact environment names required for a real staging runtime;
- fail closed on missing or obviously weak staging configuration;
- ensure local qualification artifacts are excluded from Git and Docker build context;
- make the future GCP handoff a configuration-and-deploy operation instead of another repository-cleanup phase.

## Runtime contract

`governance/staging_runtime_contract.json` contains names and policy only. It must never contain credentials, tokens, URLs with embedded credentials, key-ring material, or other secret values.

The validator reads the **current process environment** and records only variable names plus failure classes. It deliberately does not serialize secret values.

Run from repository root:

```powershell
.\scripts\Test-PMKStagingRuntimeContract.ps1
```

Expected local evidence path:

```text
.pmk-validation/stage3c-runtime-contract.json
```

A failure is expected until the eventual staging deployment environment supplies all required values. This is not a reason to weaken or commit placeholder credentials.

## Authority boundary

Stage 3C can be closed as repository/runtime preparation when its static contract and packaging protections pass CI. The environment validation itself becomes a real-staging prerequisite only when run with actual staging secret injection.

Until real GCP evidence exists:

- `RealStagingQualified = false`
- `ProductionAuthorityGranted = false`
- `Commercial Launch = NO-GO`
