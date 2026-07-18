from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_auth_bridge_attaches_supervisor_session_key_header() -> None:
    source = read_text("processual_api/static/js/admin_auth_bridge.js")

    assert "pmk_supervisor_session_key" in source
    assert "function supervisorSessionKey()" in source
    assert "const foundSupervisorSessionKey = supervisorSessionKey();" in source
    assert "X-Supervisor-Session-Key" in source
    assert "result.set('X-Supervisor-Session-Key', foundSupervisorSessionKey)" in source


def test_admin_auth_bridge_diagnostic_reports_supervisor_session_key() -> None:
    source = read_text("processual_api/static/js/admin_auth_bridge.js")

    assert "supervisorSessionKeyFound: Boolean(supervisorSessionKey())" in source
    assert "supervisorSessionKey," in source


def test_admin_client_requests_refreshes_supervisor_card_after_key_event() -> None:
    source = read_text("processual_api/static/js/admin_client_requests.js")

    assert "function refreshAdminSupervisorSessionState()" in source
    assert "pmk-supervisor-session-key-updated" in source
    assert "window.addEventListener('pmk-supervisor-session-key-updated'" in source
    assert "fetchAdminSupervisorSessionState()" in source
    assert "renderAdminSupervisorSessionSummary()" in source


def test_admin_client_request_permission_buttons_can_be_reapplied_after_refresh() -> None:
    source = read_text("processual_api/static/js/admin_client_requests.js")

    assert "data-supervisor-scope" in source or "supervisorScope" in source
    assert "refreshAdminSupervisorPermissionButtons()" in source
    assert "applyAdminSupervisorPermission(button, scope" in source
