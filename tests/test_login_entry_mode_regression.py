from pathlib import Path

LOGIN_HTML = Path("processual_api/static/login.html")


def compact_source() -> str:
    return "".join(LOGIN_HTML.read_text(encoding="utf-8").split())


def test_login_page_defaults_to_admin_when_no_query_mode_is_provided() -> None:
    source = compact_source()

    assert "functionrequestedEntryMode()" in source
    assert "newURLSearchParams(window.location.search).get('mode')" in source
    assert "returnmode==='user'?'user':'admin'" in source
    assert "letcurrentRole=requestedEntryMode()" in source
    assert "activateRole(currentRole)" in source


def test_login_page_updates_entry_mode_when_admin_tab_is_selected() -> None:
    source = compact_source()

    assert "getElementById('tab-admin').addEventListener('click',()=>activateRole('admin'))" in source
    assert "currentRole=role==='user'?'user':'admin'" in source
    assert "setEntryMode(currentRole)" in source
    assert "classList.toggle('active',currentRole==='admin')" in source


def test_login_page_updates_entry_mode_when_user_tab_is_selected() -> None:
    source = compact_source()

    assert "getElementById('tab-user').addEventListener('click',()=>activateRole('user'))" in source
    assert "classList.toggle('active',currentRole==='user')" in source
    assert "placeholder=currentRole==='admin'?'admin':'username'" in source


def test_login_page_sends_selected_role_to_auth_token_endpoint() -> None:
    source = compact_source()

    assert "JSON.stringify({username:user,password:pass,role:currentRole})" in source
    assert "sessionStorage.setItem('maestro_role',currentRole)" in source
    assert "window.location.href=currentRole==='admin'?'/admin':'/console'" in source
