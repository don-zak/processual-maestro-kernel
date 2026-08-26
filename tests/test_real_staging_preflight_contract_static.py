from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "Invoke-PMKRealStagingPreflight.ps1"
DOC = ROOT / "docs" / "REAL_GCP_CLOUD_RUN_STAGING_QUALIFICATION.md"


def test_real_staging_preflight_is_fail_closed_and_digest_pinned() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    required = [
        "gcloud auth list",
        '"run", "services", "describe"',
        '"run", "revisions", "describe"',
        "@sha256:[0-9a-fA-F]{64}$",
        "trafficPercent -ne 100",
        "/health/live",
        "/health/ready",
        "secretKeyRef",
        'qualified = $false',
        '"migration_rehearsal"',
        '"backup_restore"',
        '"rollback"',
        '"signed_go_no_go"',
    ]
    for marker in required:
        assert marker in text


def test_real_staging_contract_never_equates_preflight_with_qualification() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Synthetic CI" in text
    assert "RealStagingQualified" in text
    assert "MUST remain `false`" in text
    assert "Passing Stage 3A alone MUST NOT set `RealStagingQualified=true`" in text
    assert "mutable tag is never sufficient" in text
    assert "Release Candidate approval" in text
    assert "controlled production pilot" in text
