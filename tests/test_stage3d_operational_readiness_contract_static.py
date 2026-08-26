import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "stage3d_operational_readiness_contract.json"
SCRIPT = ROOT / "scripts" / "Test-PMKStage3DOperationalReadiness.ps1"
DOC = ROOT / "docs" / "STAGE_3D_OPERATIONAL_READINESS_PREPARATION.md"


def test_stage3d_contract_preserves_authority_boundary() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert payload["authority"]["synthetic_preparation_only"] is True
    assert payload["authority"]["real_staging_qualified"] is False
    assert payload["authority"]["production_authority_granted"] is False
    assert payload["observability"]["required_endpoints"] == [
        "/health/live",
        "/health/ready",
        "/metrics",
    ]
    assert payload["browser_e2e"]["real_browser_execution_verified"] is False
    assert payload["load_endurance"]["real_staging_load_verified"] is False
    assert payload["security"]["real_security_review_verified"] is False


def test_stage3d_validator_is_static_and_non_authoritative() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        "MISSING_OBSERVABILITY_ENDPOINT",
        "MISSING_RUNTIME_COMPONENT",
        "MISSING_PUBLIC_PAGE_ROUTE",
        "MISSING_ADMIN_PAGE_ROUTE",
        "PRODUCTION_DOCS_DISABLE_CONTRACT_MISSING",
        "WILDCARD_CORS_FAIL_CLOSED_MISSING",
        "WEAK_SECRET_POLICY_MISSING",
        "PRIVATE_RUNTIME_EXCLUSION_MISSING",
        "real_staging_qualified = $false",
        "production_authority_granted = $false",
        'load_endurance_contract = "PREPARED_NOT_EXECUTED"',
    ):
        assert marker in text

    assert "gcloud" not in text
    assert "SecretManager" not in text


def test_stage3d_documentation_does_not_claim_real_execution() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "deliberately non-authoritative for real staging and production" in text
    assert "does not prove alert delivery" in text
    assert "real browser E2E" in text
    assert "load/endurance capacity" in text
    assert "RealStagingQualified" in text
