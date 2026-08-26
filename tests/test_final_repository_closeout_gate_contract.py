from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_final_repository_closeout.ps1"


def test_final_closeout_gate_is_read_only_and_checks_all_exit_criteria() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "READ_ONLY_FINAL_REPOSITORY_RECONCILIATION_GATE" in text
    for name in (
        "REVIEW_REQUIRED",
        "SAFE_LOCAL_RESIDUE",
        "UNEXPLAINED_LOCAL_ARTIFACT",
        "UNPROTECTED_RETIRED_TOOL",
        "UNIQUE_BACKUP_CONTENT",
    ):
        assert name in text

    assert "repository_reconciliation_complete = $allZero" in text
    assert "deletion_authorized = $false" in text
    assert "real_staging_qualified = $false" in text
    assert "production_authority_granted = $false" in text
    assert "all_files_verified" in text
    assert "verified_count -eq 11" in text
    assert "source_deleted -eq $false" in text

    for destructive_token in ("Remove-Item", "Move-Item", "git clean", "git rm"):
        assert destructive_token not in text
