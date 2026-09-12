from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_controlled_real_pilot_is_not_registered_on_customer_or_evaluation_routers() -> None:
    routers_init = _text("processual_api/routers/__init__.py")
    evaluation_registry = _text("processual_api/routers/external_evaluation_route_registry.py")
    main = _text("processual_api/main.py")

    assert "controlled_real_pilot" not in routers_init
    assert "controlled_real_pilot" not in evaluation_registry
    assert "controlled-real-pilot" not in evaluation_registry
    assert "controlled_real_pilot" not in main


def test_external_evaluation_workspace_keeps_zaxam_only_embedding_contract() -> None:
    security = _text("processual_api/middleware/security_headers.py")

    assert '_EXTERNAL_EVALUATION_WORKSPACE_PATH = "/console/evaluation.html"' in security
    assert 'frame-ancestors https://zaxam.net' in security
    assert 'response.headers["X-Frame-Options"] = "DENY"' in security
    assert 'response.headers["Referrer-Policy"] = "no-referrer"' in security
    assert 'response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"' in security


def test_external_evaluation_runtime_still_requires_supervisor_issued_evaluation_identity() -> None:
    runtime = _text("processual_api/routers/evaluation_runtime.py")
    grants = _text("processual_api/routers/settings_admin_evaluation_grants.py")

    assert 'current_user.get("auth_method") != "api_key"' in runtime
    assert 'current_user.get("entitlement_source") != "admin_evaluation_grant"' in runtime
    assert 'current_user.get("subscription_required") is not False' in runtime
    assert 'Depends(require_scope("run:evaluation"))' in runtime
    assert 'detail="Governed Evaluation credential required."' in runtime

    assert 'await _require_platform_admin(request, current_user)' in grants
    assert '"entitlement_source": "admin_evaluation_grant"' in grants
    assert '"api_key": raw_key' in grants
    assert '"visible_once": True' in grants
    assert '"production_allowed": False' in grants


def test_external_evaluation_grant_cannot_authorize_controlled_real_pilot() -> None:
    pilot = _text("processual_api/services/controlled_real_pilot.py")
    executor = _text("processual_api/services/controlled_real_pilot_read_executor.py")

    assert '"external_evaluation_can_enable": False' in pilot
    assert '"production_pilot_authority_separate": True' in pilot
    assert '"external_evaluation_authority_reused": False' in pilot
    assert 'External Evaluation credentials are not accepted' in executor
    assert '"external_evaluation_authority_reused": False' in executor
