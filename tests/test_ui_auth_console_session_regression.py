from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_static(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_login_payload_uses_defined_form_values() -> None:
    html = _read_static("processual_api/static/login.html")

    assert "const user = document.getElementById('login-username').value;" in html
    assert "const pass = document.getElementById('login-password').value;" in html
    assert "body: JSON.stringify({ username: user, password: pass, role: currentRole })," in html
    assert "body: JSON.stringify({ username, password, role: currentRole })," not in html


def test_auth_login_preserves_session_token() -> None:
    js = _read_static("processual_api/static/js/auth.js")
    login_block = js.split("async function login", 1)[1].split("function logout", 1)[0]

    assert "sessionStorage.setItem(STORAGE_KEY, token);" in login_block
    assert "sessionStorage.setItem('maestro_ui_session_started_at'" in login_block
    assert "sessionStorage.removeItem(STORAGE_KEY);" not in login_block
    assert "_currentUser = { token };" in login_block
    assert "_currentUser = { token, username };" not in js


def test_client_uses_session_token_and_keeps_session_on_page_401() -> None:
    js = _read_static("processual_api/static/js/client.js")

    assert "const activeToken = _token || sessionStorage.getItem('maestro_token');" in js
    assert "headers['Authorization'] = 'Bearer ' + activeToken;" in js
    assert "res.status === 401 && _onUnauthorized && path === '/auth/me'" in js
