import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "stage3f_pre_gcp_local_closeout_contract.json"
SCRIPT = ROOT / "scripts" / "Test-PMKStage3FPreGcpLocalCloseout.ps1"
DOC = ROOT / "docs" / "STAGE_3F_PRE_GCP_FINAL_LOCAL_CLOSEOUT.md"


def test_stage3f_contract_keeps_all_authority_closed() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["authority"]["local_closeout_can_pass_without_gcp"] is True
    assert data["authority"]["real_staging_qualified"] is False
    assert data["authority"]["production_authority_granted"] is False
    assert data["authority"]["commercial_launch"] == "NO_GO"


def test_stage3f_requires_all_pre_gcp_stages_closed() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    required = data["required_repository_status"]
    assert required["stage_3b_database_recovery_rehearsal"] == ["PASS_LOCAL_REHEARSAL"]
    assert required["stage_3c_runtime_packaging_readiness"] == ["PASS_CLOSED"]
    assert required["stage_3d_operational_readiness_preparation"] == ["PASS_CLOSED"]
    assert required["stage_3e_real_staging_execution_handoff"] == ["PASS_CLOSED"]


def test_stage3f_validator_is_fail_closed_and_does_not_record_secrets() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "STAGE_NOT_CLOSED",
        "MISSING_LOCAL_EVIDENCE",
        "REAL_STAGING_AUTHORITY_MUST_REMAIN_FALSE",
        "PRODUCTION_AUTHORITY_MUST_REMAIN_FALSE",
        "COMMERCIAL_LAUNCH_MUST_REMAIN_NO_GO",
        "PMK_VALIDATION_NOT_GIT_IGNORED",
        "PMK_VALIDATION_NOT_DOCKER_IGNORED",
        "ENV_VARIANTS_NOT_DOCKER_IGNORED",
        'secret_values_recorded = $false',
        'real_staging_qualified = $false',
        'production_authority_granted = $false',
        'commercial_launch = "NO_GO"',
    ):
        assert marker in text


def test_stage3f_powershell_interpolation_is_parser_safe() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'STAGE_NOT_CLOSED:${stageName}:$($stage.status)' in text
    assert 'STAGE_NOT_CLOSED:$stageName:$($stage.status)' not in text


def test_stage3f_documentation_states_external_only_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "final local/repository closeout" in text
    assert "remaining blockers are real/external staging gates" in text
    assert "does **not** set `RealStagingQualified`" in text
    assert "signed Go/No-Go" in text
