# Real GCP / Cloud Run Staging Qualification

## Authority

This document governs Stage 3 after repository retirement and Agent Governance qualification.
Synthetic CI, Docker builds, static deployment tests, or local Docker Compose runs do not qualify real staging.

`RealStagingQualified` MUST remain `false` until every mandatory gate below has independently verifiable evidence.
`ProductionAuthorityGranted` and `Commercial Launch` remain blocked throughout staging qualification.

## Existing repository prerequisites

The repository already contains:

- `cloudbuild.yaml`, which builds and publishes Cloud Run-compatible images but deliberately does not deploy them;
- a Cloud Run-compatible `Dockerfile` using `${PORT:-8000}`;
- `/health/live` and `/health/ready` runtime probes;
- documented Secret Manager-based deployment guidance;
- static tests for the Cloud Build / Cloud Run contract.

These are prerequisites only, not real-environment proof.

## Stage 3A — Real environment preflight

Run `scripts/Invoke-PMKRealStagingPreflight.ps1` against the actual staging project, region, and Cloud Run service.

The preflight fails closed unless it can prove:

1. an authenticated `gcloud` principal exists;
2. the named Cloud Run service exists in the exact project and region;
3. a latest ready revision exists;
4. the deployed revision references an immutable `@sha256:<64-hex>` image digest rather than a mutable tag;
5. that revision receives exactly 100% of staging traffic;
6. the service URL is HTTPS;
7. `/health/live` returns `status=alive`;
8. `/health/ready` returns `status=ready`;
9. the revision contains Secret Manager references;
10. an evidence JSON receipt is written without secret values.

The receipt deliberately records `qualified=false`. Passing Stage 3A alone MUST NOT set `RealStagingQualified=true`.

Example:

```powershell
.\scripts\Invoke-PMKRealStagingPreflight.ps1 `
  -ProjectId "<staging-project-id>" `
  -Region "us-central1" `
  -Service "processual-maestro-api"
```

Default evidence path:

```text
.pmk-validation/real-staging-preflight.json
```

Do not commit that runtime evidence file unless a separate evidence-redaction and publication decision explicitly authorizes it.

## Remaining mandatory gates after Stage 3A

- migration rehearsal against the real staging PostgreSQL authority;
- backup creation and restore proof;
- rollback to a prior known-good Cloud Run revision/image digest;
- health/readiness verification after migration and rollback;
- metrics and alert verification using the real observability stack;
- external-provider integration with authorized staging credentials;
- browser E2E against the real service URL;
- load and endurance qualification;
- security review of IAM, ingress, egress, secrets, database, Redis, and public exposure;
- named human approvals;
- externally verifiable evidence bundle;
- signed Go/No-Go decision.

## Immutable-image rule

Cloud Build may create convenience tags such as `SHORT_SHA` or `latest`, but staging qualification evidence must use the digest actually attached to the Cloud Run revision. A mutable tag is never sufficient qualification authority.

## Exit condition

Only after every mandatory gate is green may the repository authority record be changed to:

```text
RealStagingQualified=true
```

That transition still does not grant production authority. Release Candidate approval and the controlled production pilot remain subsequent gates.
