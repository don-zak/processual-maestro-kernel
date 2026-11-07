# PostgreSQL Backup / Restore Qualification Runbook

This runbook defines the launch-qualification contract for PostgreSQL schema state, backup creation, backup readability, and controlled restore smoke testing.

## Safety contract

- `DATABASE_URL` is the authoritative source connection for the qualification run only. Never print it, paste it into evidence, or commit it.
- Restore qualification must use a separate disposable database supplied through `PMK_RESTORE_TEST_DATABASE_URL`.
- Never point `PMK_RESTORE_TEST_DATABASE_URL` at the authority database. The qualification harness refuses identical source/target URLs.
- The restore smoke is destructive to the disposable target because it runs `pg_restore --clean --if-exists`.
- Backups are created in PostgreSQL custom format with ownership and privilege restoration disabled for portability.
- A backup is not considered qualified merely because `pg_dump` exits zero; `pg_restore --list` must parse the archive.
- A restore is not considered qualified merely because `pg_restore` exits zero; the restored `alembic_version` table must also be readable.
- Qualification evidence must refer to the exact Git SHA being reviewed.
- This procedure does not itself authorize production release or merge.

## Migration / startup boundary

The application web startup does not run `alembic upgrade head`. Database migration is intentionally kept outside the web process so schema work cannot silently delay HTTP port binding or make liveness depend on a long migration transaction.

Before deploying an authority-service release, an operator must verify the repository Alembic heads and the target database's current revision. If the database is behind, run the intended migration as an explicit pre-deploy/operator step, then re-run qualification. Do not hide migration failures behind application startup retries.

## Prerequisites

The operator workstation must have:

- Python environment for the checked-out release source;
- Alembic installed with the project's database dependencies;
- PostgreSQL client tools `pg_dump`, `pg_restore`, and (for restore smoke) `psql`;
- `DATABASE_URL` loaded into the current process without echoing it;
- a clean checkout at the exact qualification SHA.

## 1. Schema-only qualification

```powershell
$sha = (git rev-parse HEAD).Trim()
.\scripts\qualify_postgres_recovery_winps51.ps1 -ExpectedSha $sha
```

Expected evidence:

- exact SHA PASS;
- clean working tree PASS;
- repository Alembic head(s) discovered;
- database `alembic current` includes every repository head;
- backup and restore checks SKIP because they were not requested.

A database that is behind the repository head is a FAIL, not a warning.

## 2. Backup qualification

With `DATABASE_URL` loaded securely:

```powershell
$sha = (git rev-parse HEAD).Trim()
.\scripts\qualify_postgres_recovery_winps51.ps1 `
  -ExpectedSha $sha `
  -IncludeBackup
```

The harness writes the qualification archive under `launch-hardening-results/postgres-recovery/` by default and verifies that `pg_restore --list` can parse it.

Do not treat the local qualification archive as the long-term production backup policy. The production operator must also verify the managed-platform retention/snapshot policy separately.

## 3. Controlled restore smoke

Create or select a disposable PostgreSQL database that contains no authoritative production data. Load its connection string into the current PowerShell process as `PMK_RESTORE_TEST_DATABASE_URL` without printing it.

Then run:

```powershell
$sha = (git rev-parse HEAD).Trim()
.\scripts\qualify_postgres_recovery_winps51.ps1 `
  -ExpectedSha $sha `
  -IncludeBackup `
  -IncludeRestoreSmoke
```

The restore target is cleaned before restore. The harness refuses a source/target URL equality match and validates that the restored `alembic_version` table is readable.

A successful restore smoke proves that this archive can be restored into the explicitly supplied disposable target under the current client/server/tooling contract. It does not prove managed-provider point-in-time recovery; that remains a separate hosted-platform check.

## 4. Migration execution when the database is behind

Qualification intentionally does not auto-upgrade the database. If `alembic-current` fails because the target database is behind, stop the release, capture a pre-migration backup, and run:

```powershell
python -m alembic heads
python -m alembic current
python -m alembic upgrade head
python -m alembic current
```

Run this only against the intended staged/authority database whose `DATABASE_URL` was loaded by the operator. Do not print the URL. After upgrade, repeat the PostgreSQL recovery harness and the application readiness checks.

## 5. Evidence and release gate

The harness produces:

- `launch-hardening-results/postgres-recovery/postgres-recovery-report.txt`
- `launch-hardening-results/postgres-recovery/postgres-recovery-report.json`

Record the exact SHA alongside hosted backup/PITR evidence and any restore-smoke evidence. P7 is complete only after the operator has both repository/runbook proof and executed recovery evidence for the intended launch environment.

If PostgreSQL client tooling, the source database, or the disposable restore target is unavailable, record the item as BLOCKED. Do not convert missing infrastructure into a PASS and do not weaken the recovery gate to advance a release.
