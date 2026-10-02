from pathlib import Path

SPLASH_HTML = Path("processual_api/static/splash.html")
LOGIN_HTML = Path("processual_api/static/login.html")
LOGIN_CAPTURE_JS = Path("processual_api/static/js/login_token_capture.js")


def test_splash_remains_readiness_gate_not_admin_page() -> None:
    text = SPLASH_HTML.read_text(encoding="utf-8")

    assert "Enter Maestro" in text
    assert "window.location.href = '/login'" in text
    assert "/login?mode=admin" not in text
    assert "/login?mode=user" not in text
    assert "Admin Access" not in text


def test_login_page_contains_user_admin_and_request_access_entries() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    assert 'id="tab-admin"' in text
    assert 'id="tab-user"' in text
    assert "Admin" in text
    assert "User" in text
    assert "Request access" in text
    assert 'href="/apply"' in text


def test_login_supports_optional_query_mode_selection() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    assert "new URLSearchParams(window.location.search)" in text
    assert "get('mode')" in text
    assert "return mode === 'user' ? 'user' : 'admin';" in text
    assert "activateRole(currentRole);" in text


def test_login_selected_entry_controls_destination_not_auth_role() -> None:
    html = LOGIN_HTML.read_text(encoding="utf-8")
    capture = LOGIN_CAPTURE_JS.read_text(encoding="utf-8")

    assert "sessionStorage.setItem(ENTRY_MODE_KEY, mode)" in html
    assert "pendingEntryMode = currentEntryMode()" in capture
    assert "body: JSON.stringify({ email, password })" in capture
    assert "pendingEntryMode === 'admin' ? '/admin' : '/console'" in capture
    assert "role: currentRole" not in capture
