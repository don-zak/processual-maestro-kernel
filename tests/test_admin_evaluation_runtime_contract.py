from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_grants.py"
GRANTS = ROOT / "processual_api" / "services" / "evaluation_grants.py"
SECURITY = ROOT / "processual_api" / "auth" / "security.py"
UI = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_grants.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_evaluation_runtime_keeps_key_provisioning_super_admin_only() -> None:
    source = _source(ROUTER)
    assert source.count("await require_active_platform_admin(current_user)") == 6
    assert '"authority": "platform_admin"' in source
    assert '"exclusive_super_administrator": True' in source
    assert 'created_by_admin_role": "platform_admin"' in source


def test_evaluation_runtime_is_distinct_from_commercial_production() -> None:
    router = _source(ROUTER)
    grants = _source(GRANTS)
    ui = _source(UI)

    assert 'EVALUATION_EXECUTION_MODE = "evaluation_runtime"' in router
    assert '"real_runtime_execution": True' in router
    assert '"production_allowed": False' in router
    assert 'EVALUATION_EXECUTION_MODE = "evaluation_runtime"' in grants
    assert "evaluation_runtime" in ui
    assert "commercial production" in ui.lower()


def test_selected_endpoints_are_persisted_and_enforced_at_auth_boundary() -> None:
    router = _source(ROUTER)
    grants = _source(GRANTS)
    security = _source(SECURITY)
    ui = _source(UI)

    assert "allowed_endpoints: list[EvaluationEndpointSelection]" in router
    assert "get_api_key_access_policy(method, path)" in router
    assert '"endpoint_authority_source": "canonical_runtime_access_policy"' in router
    assert "requested_endpoints=endpoints" in router
    assert "evaluation_endpoint_allowed" in grants
    assert "evaluation_endpoint_allowed(" in security
    assert "Evaluation grant does not allow this runtime endpoint." in security
    assert "allowed_endpoints: readiness.endpoints.map" in ui


def test_control_plane_cannot_enter_evaluation_endpoint_catalog() -> None:
    source = _source(ROOT / "processual_api" / "integrations" / "api_key_access_policy.py")
    assert 'normalized_path.startswith(("/settings", "/admin", "/auth"))' in source
    assert "Control-plane routes may not be API-key grantable" in source
