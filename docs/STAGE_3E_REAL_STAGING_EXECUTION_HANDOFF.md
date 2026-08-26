# Stage 3E — Real-Staging Execution Handoff

Stage 3E turns the completed local qualification work into one deterministic operator entry point while preserving the boundary between preparation and real staging.

## Prepare mode

Run after Stage 3B local evidence exists:

```powershell
.\scripts\Invoke-PMKStage3ERealStagingHandoff.ps1 -Mode Prepare
```

This mode verifies the Stage 3B recovery evidence and executes the Stage 3D static/local operational-readiness validator. It does not need GCP, billing, or real secrets and never sets `RealStagingQualified=true`.

To additionally validate an injected staging-style runtime environment, use:

```powershell
.\scripts\Invoke-PMKStage3ERealStagingHandoff.ps1 -Mode Prepare -ValidateRuntimeEnvironment
```

No secret values are written to evidence.

## Real GCP mode

Only after billing and the real staging service exist:

```powershell
.\scripts\Invoke-PMKStage3ERealStagingHandoff.ps1 `
  -Mode RealGcp `
  -ProjectId <PROJECT_ID> `
  -Region <REGION> `
  -Service <SERVICE>
```

The command fails closed unless all three target values are supplied. It then invokes the repository's real Cloud Run preflight. The target is explicit; the script does not invent a project, region, or service.

## Authority boundary

Even a successful real preflight is not final real-staging qualification. Managed database migration and recovery, real secret injection, alert delivery, external-provider integration, real browser E2E, real load/endurance, security review, named human approvals, and signed Go/No-Go remain separate gates.
