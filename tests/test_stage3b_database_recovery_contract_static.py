from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "Invoke-PMKStage3BDatabaseRecoveryRehearsal.ps1"
DOC = ROOT / "docs" / "STAGE_3B_DATABASE_RECOVERY_REHEARSAL.md"


def test_stage3b_script_is_fail_closed_and_non_authoritative() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    required = [
        "postgres:16",
        'Invoke-Docker -Arguments @(\"pull\", \"postgres:16\")',
        "python -m alembic upgrade head",
        "pg_dump",
        "--format=custom",
        "pg_restore",
        "backup_sha256",
        "migration_rehearsal = \"PASS\"",
        "restore_verification = \"PASS\"",
        "rollback_to_snapshot = \"PASS\"",
        "rollback_mutation_absent = $true",
        "qualified = $false",
        "synthetic_rehearsal_only = $true",
        "real_staging_qualified = $false",
    ]
    for marker in required:
        assert marker in text

    assert "POSTGRES_PASSWORD=$password" in text
    assert "processual-maestro-staging" not in text
    assert "gcloud" not in text


def test_stage3b_native_docker_stderr_uses_exit_code_as_authority() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '$previousErrorActionPreference = $ErrorActionPreference' in text
    assert '$ErrorActionPreference = "Continue"' in text
    assert "$exitCode = $LASTEXITCODE" in text
    assert "if ($exitCode -ne 0)" in text
    assert "ForEach-Object { $_.ToString() }" in text


def test_stage3b_rollback_proves_post_snapshot_mutation_is_absent() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "stage3b_post_snapshot_mutation" in text
    assert "tablename='stage3b_post_snapshot_mutation'" in text
    assert '$mutationCount -ne "0"' in text
    assert "mutated-after-snapshot" in text
    assert '$rollbackSentinel -ne "snapshot-ok"' in text


def test_stage3b_documentation_preserves_real_staging_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "synthetic/local qualification prerequisite" in text
    assert "does not replace the real GCP / Cloud Run staging gates" in text
    assert '"qualified": false' in text
    assert '"real_staging_qualified": false' in text
    assert "production backups" in text
