from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"
SCRIPT = STATIC_DIR / "js" / "admin_client_requests.js"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_admin_direct_client_plan_panel_is_rendered_from_request_detail() -> None:
    script = _script()

    required = [
        "DIRECT_ADMIN_PLAN_OPTIONS",
        "renderAdminDirectClientPlanPanel",
        "renderAdminDirectClientPlanPanel(detail, body)",
        "admin-direct-client-plan",
        "admin-direct-client-plan-select",
        "admin-direct-client-plan-button",
        "Direct Client Plan",
        "Set direct plan",
        "plan_source=settings",
        "pricing catalog",
    ]

    for token in required:
        assert token in script


def test_admin_direct_client_plan_posts_to_direct_client_plan_route() -> None:
    script = _script()

    required = [
        "function directClientPlanPath(clientId)",
        "'/settings/admin/clients/'",
        "+ '/plan'",
        "postJson(directClientPlanPath(clientId), { plan_id: planId })",
        "monthly_unit_allowance",
        "plan_source",
        "plan_set",
    ]

    for token in required:
        assert token in script


def test_admin_direct_client_plan_uses_supervisor_decide_scope() -> None:
    script = _script()

    required = [
        "button.dataset.supervisorScope = CLIENTS_STATUS_DECIDE_SCOPE",
        "applyAdminSupervisorPermission(",
        "Requires supervisor scope: ",
        "CLIENTS_STATUS_DECIDE_SCOPE",
    ]

    for token in required:
        assert token in script


def test_admin_direct_client_plan_cache_version_is_updated() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "admin_client_requests.js?v=admindirectplan07" in html
    assert "admin_client_requests.js?v=adminapplyplan02" not in html


def test_admin_direct_client_plan_ui_does_not_expose_secret_markers() -> None:
    script = _script()

    forbidden = [
        "provider_secret",
        "encrypted_key",
        "api_key",
        "apiKey",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "MAESTRO_ADMIN_PASSWORD",
    ]

    present = [token for token in forbidden if token in script]
    assert not present, f"Admin direct client plan UI exposes forbidden markers: {present}"
