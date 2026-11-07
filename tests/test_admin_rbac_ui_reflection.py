from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_CLIENT_REQUESTS_JS = Path("processual_api/static/js/admin_client_requests.js")


def _admin_html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def _client_requests_js() -> str:
    return ADMIN_CLIENT_REQUESTS_JS.read_text(encoding="utf-8")


def test_admin_home_exposes_supervisor_session_summary_panel() -> None:
    html = _admin_html()

    assert "admin-supervisor-session-card" in html
    assert "admin-supervisor-session-status" in html
    assert "admin-supervisor-session-level" in html
    assert "admin-supervisor-session-scopes" in html
    assert "Supervisor Session" in html
    assert "Backend enforcement remains authoritative" in html


def test_admin_client_requests_uses_canonical_auth_bridge_without_legacy_header_fallback() -> None:
    script = _client_requests_js()

    assert "SUPERVISOR_SESSION_KEY_STORAGE_KEYS" in script
    assert "getAdminSupervisorSessionKey" in script
    assert "pmk_supervisor_session_key" in script
    assert "authHeaders" in script
    assert "window.PMK_ADMIN_AUTH" in script
    assert "return { ...(extra || {}) };" in script
    assert "X-Supervisor-Session-Key" not in script
    assert "admin_supervisor_session_key" not in script
    assert "localStorage.getItem('access_token')" not in script
    assert "sessionStorage.getItem('access_token')" not in script


def test_admin_client_request_ui_defines_supervisor_scope_model() -> None:
    script = _client_requests_js()

    required = [
        "ADMIN_SUPERVISOR_SCOPES",
        "admin:clients:status_review",
        "admin:clients:status_decide",
        "admin:clients:draft",
        "admin:clients:respond",
        "review_supervisor",
        "operations_supervisor",
        "owner_supervisor",
        "canAdminSupervisorUse",
        "applyAdminSupervisorPermission",
        "data-required-scope",
        "data-disabled-reason",
        "Requires supervisor scope",
    ]

    for marker in required:
        assert marker in script


def test_admin_client_request_status_buttons_reflect_review_and_decide_permissions() -> None:
    script = _client_requests_js()

    assert "renderAdminClientRequestStatusActions" in script
    assert "CLIENTS_STATUS_REVIEW_SCOPE" in script
    assert "CLIENTS_STATUS_DECIDE_SCOPE" in script
    assert "nextStatus === 'reviewed'" in script
    assert "applyAdminSupervisorPermission(button" in script


def test_admin_client_request_draft_and_send_buttons_reflect_permissions() -> None:
    script = _client_requests_js()

    assert "renderAdminClientRequestResponseDraftPanel" in script
    assert "CLIENTS_DRAFT_SCOPE" in script
    assert "CLIENTS_RESPOND_SCOPE" in script
    assert "applyAdminSupervisorPermission(generate" in script
    assert "applyAdminSupervisorPermission(save" in script
    assert "applyAdminSupervisorPermission(send" in script


def test_admin_client_request_script_exposes_supervisor_ui_helpers_for_regression() -> None:
    script = _client_requests_js()

    assert "renderAdminSupervisorSessionSummary" in script
    assert "fetchAdminSupervisorSessionState" in script
    assert "/auth/me" in script
    assert "PMK_ADMIN_CLIENT_REQUESTS_RBAC_UI" in script
