from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_browser_loads_supervisor_flow_scripts_in_order() -> None:
    source = read_text("processual_api/static/admin.html")

    auth_bridge = source.index("admin_auth_bridge.js")
    admin_session = source.index("admin_session.js")
    client_requests = source.index("admin_client_requests.js")
    api_keys = source.index("admin_api_keys.js")

    assert auth_bridge < admin_session
    assert auth_bridge < client_requests
    assert auth_bridge < api_keys
    assert "admin-supervisor-session-status" in source
    assert "admin-supervisor-session-level" in source
    assert "admin-supervisor-session-scopes" in source


def test_api_keys_page_exposes_explicit_use_and_clear_browser_session_flow() -> None:
    source = read_text("processual_api/static/js/admin_api_keys.js")

    assert "pmk_supervisor_session_key" in source
    assert "Use this key for this browser session" in source
    assert "sessionStorage.setItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY, raw)" in source
    assert "sessionStorage.removeItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY)" in source
    assert "pmk-supervisor-session-key-updated" in source
    assert "dispatchSupervisorSessionKeyUpdated()" in source


def test_auth_bridge_carries_supervisor_key_for_auth_and_settings_round_trips() -> None:
    source = read_text("processual_api/static/js/admin_auth_bridge.js")

    assert "function supervisorSessionKey()" in source
    assert "pmk_supervisor_session_key" in source
    assert "X-Supervisor-Session-Key" in source
    assert "target.pathname.startsWith('/auth/')" in source
    assert "target.pathname.startsWith('/settings/')" in source
    assert "nextInit.headers = headers(sourceHeaders)" in source
    assert "installFetchBridge()" in source


def test_supervisor_key_event_refreshes_card_and_rbac_buttons() -> None:
    source = read_text("processual_api/static/js/admin_client_requests.js")

    assert "window.addEventListener('pmk-supervisor-session-key-updated'" in source
    assert "refreshAdminSupervisorSessionState()" in source
    assert "fetchAdminSupervisorSessionState()" in source
    assert "request('/auth/me')" in source
    assert "renderAdminSupervisorSessionSummary()" in source
    assert "refreshAdminSupervisorPermissionButtons()" in source
    assert "button.dataset.supervisorScope = scope" in source


def test_clients_surface_reflects_review_and_operations_supervisor_permissions() -> None:
    source = read_text("processual_api/static/js/admin_client_requests.js")

    assert "review_supervisor" in source
    assert "operations_supervisor" in source
    assert "admin:clients:status_review" in source
    assert "admin:clients:status_decide" in source
    assert "admin:clients:draft" in source
    assert "admin:clients:respond" in source
    assert "Requires supervisor scope" in source
    assert "data-disabled-reason" in source
