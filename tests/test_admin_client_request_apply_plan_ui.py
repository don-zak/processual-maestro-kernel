from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "processual_api" / "static"
SCRIPT = STATIC_DIR / "js" / "admin_client_requests.js"


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_admin_client_request_apply_plan_ui_tokens_present() -> None:
    script = _script()

    required = [
        "applyPlanPath",
        "/apply-plan",
        "renderAdminClientRequestApplyPlanPanel",
        "applyAdminClientRequestRequestedPlan",
        "admin-client-request-apply-plan-button",
        "Apply requested plan",
        "postJson(applyPlanPath(requestId), {})",
        "renderAdminClientRequestDetail(data?.request || {})",
        "CLIENTS_STATUS_DECIDE_SCOPE",
    ]
    for token in required:
        assert token in script


def test_admin_client_request_apply_plan_visibility_guard() -> None:
    script = _script()

    required = [
        "canShowAdminClientRequestApplyPlan",
        "requested_plan",
        "approved",
        "completed",
        "plan_applied",
        "!detail?.plan_applied",
        "Ready to apply requested plan.",
        "Requested plan already applied.",
    ]
    for token in required:
        assert token in script


def test_admin_client_request_detail_renders_plan_application_fields() -> None:
    script = _script()

    for token in [
        "approved_plan",
        "plan_source",
        "plan_applied",
        "plan_applied_at",
        "plan_applied_by",
    ]:
        assert token in script

    assert "text(item?.status || item?.event || 'pending')" in script
    assert "renderAdminClientRequestApplyPlanPanel(detail, body)" in script


def test_admin_client_request_apply_plan_uses_supervisor_decide_scope() -> None:
    script = _script()

    assert "button.dataset.supervisorScope = CLIENTS_STATUS_DECIDE_SCOPE" in script
    assert "applyAdminSupervisorPermission(" in script
    assert "Requires supervisor scope: " in script


def test_admin_client_request_apply_plan_cache_version_is_updated() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_client_requests.js" in html
    assert "admindirectplan07" in html


def test_admin_client_request_apply_plan_ui_keeps_forbidden_markers_out() -> None:
    script = _script()

    forbidden = [
        "provider_secret",
        "encrypted_key",
        "raw key",
        "/settings/llm-provider",
    ]
    for token in forbidden:
        assert token not in script


def test_admin_client_request_apply_plan_permissions_use_auth_me_scopes() -> None:
    script = _script()

    assert "adminSupervisorSessionState.user.scopes" in script
    assert "const scopes = [...new Set([...rawScopes, ...authUserScopes])];" in script
    assert "refreshAdminSupervisorPermissionButtons();" in script
    assert "admin-client-request-action-scope-note" in script
    assert "admin:clients:status_decide" in script
