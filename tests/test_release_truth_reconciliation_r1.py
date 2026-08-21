from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FINAL_READINESS = ROOT / "FINAL_READINESS_REPORT.md"
EXTERNAL_READINESS = ROOT / "EXTERNAL_READINESS_REPORT.md"
RELEASE_NOTES = ROOT / "RELEASE_NOTES.md"


def test_historical_final_readiness_is_non_authoritative() -> None:
    text = FINAL_READINESS.read_text(encoding="utf-8")

    assert "HISTORICAL / NON-AUTHORITATIVE" in text
    assert "does **not** describe" in text
    assert "Real Staging" in text
    assert "ProductionAuthorityGranted" in text


def test_external_readiness_is_reconciled_to_current_boundary() -> None:
    text = EXTERNAL_READINESS.read_text(encoding="utf-8")

    assert "QUALIFICATION SNAPSHOT — NOT PRODUCTION AUTHORITY" in text
    assert "sanitized six-field contract" in text
    assert "Visual Qualification Gate V1 (VQ-1)" in text
    assert "RealStagingQualified=false" in text
    assert "ProductionAuthorityGranted=false" in text

    assert "migrating from stubs to full engine requires the proprietary" not in text
    assert "10 pre-existing test failures" not in text
    assert "Auth-protected endpoints | 45 (100%)" not in text


def test_release_notes_do_not_reintroduce_historical_full_image_authority() -> None:
    text = RELEASE_NOTES.read_text(encoding="utf-8")

    assert "QUALIFICATION NOTES — NOT A RELEASE OR PRODUCTION AUTHORITY" in text
    assert "Visual Qualification Gate V1 (VQ-1)" in text
    assert "immutable image digest" in text
    assert "ProductionAuthorityGranted=false" in text

    assert "docker build --target full" not in text
    assert "Full (includes CGT engine" not in text
    assert "CGT endpoints return `503` with" not in text
