from pathlib import Path

LOGIN_HTML = Path("processual_api/static/login.html")


def test_login_page_defaults_to_admin_when_no_query_mode_is_provided() -> None:
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "function requestedEntryMode()" in source
    assert "new URLSearchParams(window.location.search).get('mode')" in source
    assert "return mode === 'user' ? 'user' : 'admin';" in source
    assert "let currentRole = requestedEntryMode();" in source
    assert "activateRole(currentRole);" in source


def test_login_page_updates_entry_mode_when_admin_tab_is_selected() -> None:
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "document.getElementById('tab-admin').addEventListener('click', () => activateRole('admin'));" in source
    assert "currentRole = role === 'user' ? 'user' : 'admin';" in source
    assert "setEntryMode(currentRole);" in source
    assert "classList.toggle('active', currentRole === 'admin')" in source


def test_login_page_updates_entry_mode_when_user_tab_is_selected() -> None:
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "document.getElementById('tab-user').addEventListener('click', () => activateRole('user'));" in source
    assert "classList.toggle('active', currentRole === 'user')" in source
    assert "placeholder = currentRole === 'admin' ? 'admin' : 'username';" in source


def test_login_page_sends_selected_role_to_auth_token_endpoint() -> None:
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "JSON.stringify({ username: user, password: pass, role: currentRole })" in source
    assert "sessionStorage.setItem('maestro_role', currentRole)" in source
