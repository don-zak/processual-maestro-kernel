from __future__ import annotations

from pathlib import Path

SCRIPT = Path("scripts/qualify_postgres_recovery_winps51.ps1")


def test_postgres_recovery_harness_is_fail_closed_and_secret_safe() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "PMK_RESTORE_TEST_DATABASE_URL" in text
    assert "Restore target must be a separate database" in text
    assert "source and target URLs are identical" in text
    assert "--format=custom" in text
    assert "--no-owner" in text
    assert "--no-privileges" in text
    assert "pg_restore --list" in text
    assert "--exit-on-error" in text
    assert "SELECT version_num FROM alembic_version" in text
    assert "value redacted" in text
    assert "<redacted>" in text
    assert "OVERALL BLOCKED" in text
    assert "OVERALL FAIL" in text


def test_postgres_recovery_harness_exposes_only_sanitized_diagnostics() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "function Get-SafeDiagnostic" in text
    assert "diagnostic={1}" in text
    assert "postgres(?:ql)?" in text
    assert "PGPASSWORD" in text
    assert "...<truncated>" in text
    assert "Get-SafeDiagnostic $current.text" in text
    assert "Get-SafeDiagnostic $backupResult.text" in text
    assert "Get-SafeDiagnostic $restoreResult.text" in text


def test_postgres_recovery_harness_does_not_print_connection_urls() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden = (
        "Write-Host $sourceUrl",
        "Write-Host $targetUrl",
        "Write-Output $sourceUrl",
        "Write-Output $targetUrl",
        '"DATABASE_URL=$sourceUrl"',
        '"PMK_RESTORE_TEST_DATABASE_URL=$targetUrl"',
    )
    for marker in forbidden:
        assert marker not in text


def test_postgres_recovery_harness_restores_pg_environment() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-WithPgEnvironment" in text
    assert "finally" in text
    assert "SetEnvironmentVariable($name, $before[$name], 'Process')" in text
    assert "return (& $Script)" in text
