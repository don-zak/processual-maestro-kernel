from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js")


def _html() -> str:
    return ADMIN_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return ADMIN_API_KEYS_JS.read_text(encoding="utf-8")


def test_admin_api_keys_cache_bumped_for_supervisor_key_ui() -> None:
    html = _html()

    assert "admin_api_keys.js?v=adminsuperkeysux02" in html


def test_supervisor_session_key_panel_is_added_to_api_keys_page() -> None:
    script = _script()

    required = [
        "SUPERVISOR_SESSION_KEY_ENDPOINT",
        "SUPERVISOR_SESSION_KEY_FIELDS",
        "renderSupervisorSessionKeyPanel",
        "Supervisor Session Keys",
        "admin-supervisor-key-level",
        "admin-supervisor-key-issued-to",
        "admin-supervisor-key-label",
        "admin-supervisor-key-reason",
        "admin-supervisor-key-expires-at",
        "admin-supervisor-key-issue-btn",
        "admin-supervisor-key-refresh-btn",
        "admin-supervisor-key-create-result",
        "admin-supervisor-key-table",
    ]

    for marker in required:
        assert marker in script


def test_supervisor_session_key_ui_calls_backend_lifecycle_endpoints() -> None:
    script = _script()

    required = [
        "issueSupervisorSessionKey",
        "refreshSupervisorSessionKeys",
        "revokeSupervisorSessionKey",
        "request('POST', SUPERVISOR_SESSION_KEY_ENDPOINT",
        "request('GET', SUPERVISOR_SESSION_KEY_ENDPOINT",
        "request('POST', `${SUPERVISOR_SESSION_KEY_ENDPOINT}/${sessionKeyId}/revoke`",
    ]

    for marker in required:
        assert marker in script


def test_supervisor_session_key_ui_renders_one_time_raw_key_only_in_create_result() -> None:
    script = _script()

    required = [
        "renderOneTimeSupervisorSessionKey",
        "One-time supervisor session key created.",
        "X-Supervisor-Session-Key:",
        "admin-supervisor-key-copy-created",
        "Copy Supervisor Key",
        "raw_key",
    ]

    for marker in required:
        assert marker in script


def test_supervisor_session_key_safe_table_avoids_secret_material_fields() -> None:
    script = _script()

    fields_start = script.index("const SUPERVISOR_SESSION_KEY_FIELDS = [")
    fields_end = script.index("];", fields_start)
    fields_block = script[fields_start:fields_end]

    assert "session_key_id" in fields_block
    assert "level" in fields_block
    assert "issued_to" in fields_block
    assert "revoked_at" in fields_block
    assert "last_used_at" in fields_block
    assert "raw_key" not in fields_block
    assert "key_hash" not in fields_block
    assert "encrypted_key" not in fields_block
    assert "provider_secret" not in fields_block


def test_supervisor_session_key_ui_wires_controls_and_revoke_buttons() -> None:
    script = _script()

    required = [
        "admin-supervisor-key-issue-btn",
        "addEventListener('click', issueSupervisorSessionKey)",
        "admin-supervisor-key-refresh-btn",
        "addEventListener('click', refreshSupervisorSessionKeys)",
        "admin-supervisor-key-revoke",
        "button.dataset.sessionKeyId",
    ]

    for marker in required:
        assert marker in script



def test_supervisor_session_key_ui_can_store_and_clear_browser_session_key() -> None:
    html = _html()
    script = _script()

    assert "admin-supervisor-session-clear-key" in html

    required = [
        "SUPERVISOR_SESSION_KEY_STORAGE_KEY",
        "pmk_supervisor_session_key",
        "storeSupervisorSessionKeyForAdmin",
        "sessionStorage.setItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY, raw)",
        "clearSupervisorSessionKeyForAdmin",
        "sessionStorage.removeItem(SUPERVISOR_SESSION_KEY_STORAGE_KEY)",
        "admin-supervisor-key-use-created",
        "Use this key for this browser session",
        "admin-supervisor-key-clear-session",
        "Clear supervisor session key",
        "updateSupervisorSessionCardAfterUse",
        "pmk-supervisor-session-key-updated",
    ]

    for marker in required:
        assert marker in script
