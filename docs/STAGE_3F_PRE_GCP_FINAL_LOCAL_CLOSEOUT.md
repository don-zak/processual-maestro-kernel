# Stage 3F — Pre-GCP Final Local Closeout

Stage 3F is the final local/repository closeout before real GCP qualification resumes.

It verifies that Stage 3B, Stage 3C, Stage 3D, and Stage 3E are closed in repository status, that required local evidence is present, and that local evidence / environment material cannot enter Git or the Docker build context.

Run from repository root:

```powershell
.\scripts\Test-PMKStage3FPreGcpLocalCloseout.ps1
```

Expected evidence:

- `.pmk-validation/stage3f-pre-gcp-local-closeout.json`

A PASS means only that all remaining blockers are real/external staging gates. It does **not** set `RealStagingQualified`, grant production authority, or allow commercial launch.

After Stage 3F, the remaining path is external-only: GCP billing, explicit real target, secret injection, managed database migration/recovery, alert delivery, external-provider integration, real browser E2E, real load/endurance, real security review, named human approvals, and signed Go/No-Go.
