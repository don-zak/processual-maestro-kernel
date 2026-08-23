import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "Invoke-PMKStage3ERealStagingHandoff.ps1"
CONTRACT = ROOT / "governance" / "stage3e_real_staging_handoff_contract.json"
DOC = ROOT / "docs" / "STAGE_3E_REAL_STAGING_EXECUTION_HANDOFF.md"


def test_stage3e_contract_preserves_authority_boundary() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["authority"]["prepare_mode_can_run_without_gcp"] is True
    assert data["authority"]["real_gcp_mode_requires_explicit_target"] is True
    assert data["authority"]["secret_values_recorded"] is False
    assert data["authority"]["real_staging_qualified"] is False
    assert data["authority"]["production_authority_granted"] is False


def test_stage3e_script_requires_local_recovery_evidence_and_explicit_real_target() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "STAGE_3B_DATABASE_RECOVERY_REHEARSAL",
        "migration_rehearsal",
        "restore_verification",
        "rollback_to_snapshot",
        "Test-PMKStage3DOperationalReadiness.ps1",
        "Test-PMKStagingRuntimeContract.ps1",
        "Invoke-PMKRealStagingPreflight.ps1",
        "MISSING_REAL_TARGET",
        'real_staging_qualified = $false',
        'production_authority_granted = $false',
        'secret_values_recorded = $false',
    ):
        assert marker in text

    assert "-ProjectId $ProjectId" in text
    assert "-Region $Region" in text
    assert "-Service $Service" in text


def test_stage3e_documentation_keeps_prepare_and_real_modes_separate() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "Prepare mode" in text
    assert "Real GCP mode" in text
    assert "does not need GCP" in text
    assert "does not invent a project, region, or service" in text
    assert "successful real preflight is not final real-staging qualification" in text
