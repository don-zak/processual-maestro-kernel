from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "archive_backup_evidence.ps1"


def test_backup_archive_is_external_copy_verify_without_source_deletion() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "COPY_VERIFY_EXTERNAL_ARCHIVE" in text
    assert "Copy-Item" in text
    assert "Get-FileHash" in text
    assert "archive-receipt.json" in text
    assert "all_files_verified = $allVerified" in text
    assert "source_deleted = $false" in text
    assert "deletion_authorized = $false" in text
    assert "unique_backup_content_resolved = $allVerified" in text
    assert "ArchiveRoot must be outside the repository root" in text
    assert "Remove-Item" not in text
    assert "Move-Item" not in text
    assert "git clean" not in text
    assert "git rm" not in text
