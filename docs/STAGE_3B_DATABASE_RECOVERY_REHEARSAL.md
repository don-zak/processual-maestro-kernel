# Stage 3B — Database Recovery Rehearsal

Stage 3B is a **synthetic/local qualification prerequisite** for real staging. It does not replace the real GCP / Cloud Run staging gates and it never sets `RealStagingQualified=true`.

## Scope

The rehearsal proves, on an ephemeral PostgreSQL 16 instance:

1. the current repository can apply `alembic upgrade head` to a fresh PostgreSQL database;
2. a custom-format `pg_dump` snapshot can be captured after migration;
3. the snapshot restores into an independent database with the same Alembic head and sentinel data;
4. a post-snapshot mutation can be discarded by restoring the snapshot into a clean rollback database;
5. the resulting evidence records the snapshot SHA-256 and remains explicitly non-authoritative for real staging.

## Run

From the repository root on Windows PowerShell:

```powershell
.\scripts\Invoke-PMKStage3BDatabaseRecoveryRehearsal.ps1
```

Requirements:

- Docker Desktop / Docker Engine;
- Python environment with the repository dependencies and Alembic installed;
- no production database credentials are required or accepted by the script.

Outputs:

- `.pmk-validation/stage3b-database-recovery.json`
- `.pmk-validation/stage3b-postgres.snapshot.dump`

Both outputs are local qualification artifacts and must not be treated as production backups.

## Fail-closed contract

The script fails if any of the following is not proven:

- PostgreSQL 16 becomes ready;
- `alembic upgrade head` succeeds;
- `alembic_version` is readable;
- the dump is non-empty and hashable;
- restored sentinel data exactly matches the snapshot;
- restored Alembic head exactly matches the source;
- rollback recovery restores the snapshot sentinel;
- a mutation created after the snapshot is absent after rollback restore.

The evidence always contains:

```json
{
  "qualified": false,
  "synthetic_rehearsal_only": true,
  "real_staging_qualified": false
}
```

## Remaining authority boundary

Even after Stage 3B passes, real staging still requires the actual GCP environment and independent evidence for managed-database migration, backup/restore, rollback, observability, external-provider integration, browser E2E, load/endurance, security review, named human approvals, and signed Go/No-Go.
