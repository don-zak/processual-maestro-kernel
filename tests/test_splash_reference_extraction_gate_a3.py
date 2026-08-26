import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_extraction_contract_a3.json"
SPLASH = ROOT / "processual_api" / "static" / "splash.html"
EXTRACTOR = ROOT / "scripts" / "extract_splash_reference_routes.py"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_reference_extraction_contract_is_locked_to_approved_image_geometry() -> None:
    contract = _contract()
    assert contract["source_of_truth"] == "approved pivot reference image"
    assert contract["reference_size"] == [1672, 941]
    assert contract["reference_core_bounds"] == [608, 224, 1041, 632]
    assert EXTRACTOR.exists()


def test_splash_reconstruction_cannot_resume_before_canonical_manifest_audit() -> None:
    contract = _contract()
    if SPLASH.exists():
        assert contract["canonical_manifest_ready"] is True
        assert contract["splash_reconstruction_allowed"] is True
        assert contract["current_status"] == "CANONICAL"
    else:
        assert contract["current_status"] == "AUDIT_REQUIRED"
        assert contract["canonical_manifest_ready"] is False
        assert contract["splash_reconstruction_allowed"] is False


def test_shortcut_generation_methods_remain_forbidden() -> None:
    contract = _contract()
    forbidden = set(contract["prohibited_shortcuts"])
    assert "procedural-route-generation" in forbidden
    assert "hand-authored-reference-approximation" in forbidden
    assert "invented-route-topology" in forbidden
    assert "splash-reconstruction-before-audit" in forbidden
