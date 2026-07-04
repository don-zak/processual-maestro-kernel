from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"
SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_client_account_identity_fields_are_visible() -> None:
    html = read_file(INDEX_HTML)

    assert "Current client session identity" in html
    assert 'data-settings-section-key="account"' in html
    assert 'id="set-account-user"' in html
    assert 'id="set-account-role"' in html
    assert 'id="set-account-session"' in html
    assert 'id="set-account-client-id"' in html
    assert 'id="set-account-session-type"' in html
    assert 'id="set-account-scopes"' in html
    assert 'id="set-account-status"' in html
    assert "Client ID" in html
    assert "Session Type" in html
    assert "Scopes" in html
    assert "Identity Status" in html


def test_client_account_identity_runtime_uses_auth_me_payload() -> None:
    js = read_file(SETTINGS_JS)

    assert "CLIENT.get('/auth/me')" in js
    assert "function accountIdentityValue(account)" in js
    assert "function accountClientId(account)" in js
    assert "function accountScopes(account)" in js
    assert "account.user_id || account.client_id || account.sub" in js
    assert "account.client_id || account.user_id || account.sub" in js
    assert "me.session_type || 'ui_client'" in js
    assert "set-account-client-id" in js
    assert "set-account-session-type" in js
    assert "set-account-scopes" in js
    assert "set-account-status" in js


def test_client_account_identity_has_safe_fallbacks() -> None:
    js = read_file(SETTINGS_JS)

    assert "Fallback session identity" in js
    assert "Verified via /auth/me" in js
    assert "setText('set-account-client-id', '-')" in js
    assert "setText('set-account-session-type', 'ui_client')" in js
    assert "setText('set-account-scopes', 'evaluation')" in js
    assert "readinessState.account = { role: sessionRole(), fallback: true }" in js
