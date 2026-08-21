from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_private_http_errors_are_generic_and_bounded() -> None:
    source = (
        ROOT / "processual_api/integrations/private_evaluation_http.py"
    ).read_text(encoding="utf-8")

    assert 'detail="private_evaluation_contract_violation"' in source
    assert 'detail="private_evaluation_unavailable"' in source
    assert "str(exc)" not in source
    assert "repr(exc)" not in source
    assert "traceback" not in source.lower()


def test_boundary_discards_provider_exception_details() -> None:
    source = (
        ROOT / "processual_api/integrations/private_evaluation_boundary.py"
    ).read_text(encoding="utf-8")

    assert "except Exception:" in source
    assert 'PrivateEvaluationUnavailableError("private_evaluation_unavailable")' in source
    assert "raise PrivateEvaluationUnavailableError" in source
    assert "from exc" not in source
    assert "str(exc)" not in source
    assert "repr(exc)" not in source


def test_public_boundary_does_not_name_private_math_in_error_contract() -> None:
    http_source = (
        ROOT / "processual_api/integrations/private_evaluation_http.py"
    ).read_text(encoding="utf-8")
    boundary_source = (
        ROOT / "processual_api/integrations/private_evaluation_boundary.py"
    ).read_text(encoding="utf-8")
    public_error_surface = http_source + "\n" + boundary_source

    forbidden = (
        "raw_score",
        "fate_vector",
        "threshold_value",
        "calibration_value",
        "private_equation",
        "private_weight",
    )
    assert not any(token in public_error_surface for token in forbidden)
