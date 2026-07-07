from pathlib import Path

LOGIN_HTML = Path("processual_api/static/login.html")


def _login_text() -> str:
    return LOGIN_HTML.read_text(encoding="utf-8")


def test_login_gateway_commercial_and_recovery_actions_exist() -> None:
    text = _login_text()

    assert 'id="login-commercial-actions"' in text
    assert 'id="login-offers-registration-button"' in text
    assert 'id="login-lost-access-button"' in text
    assert 'data-en="Offers &amp; Registration"' in text
    assert 'data-ar="العروض والتسجيل"' in text
    assert 'data-en="Lost Access?"' in text
    assert 'data-ar="فقدت بيانات الدخول؟"' in text


def test_login_gateway_actions_are_secondary_buttons_not_checkout_links() -> None:
    text = _login_text().lower()

    assert 'type="button"' in text
    assert "data-login-panel-target" in text
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text
    assert "lemonsqueezy" not in text
    assert "lemon_squeezy" not in text


def test_login_gateway_recovery_copy_is_safe_and_non_enumerating() -> None:
    text = _login_text().lower()

    assert "if an account exists" in text
    assert "reset password" not in text
    assert "new password" not in text
    assert "temporary password" not in text


def test_login_gateway_keeps_admin_user_entry_modes() -> None:
    text = _login_text()

    assert 'id="tab-admin"' in text
    assert 'id="tab-user"' in text
    assert "Admin" in text
    assert "User" in text


def test_login_gateway_preserves_request_access_link() -> None:
    text = _login_text()

    assert 'href="/apply"' in text
    assert 'aria-label="Request access"' in text
    assert "Request access" in text


def test_login_gateway_actions_are_below_sign_in_copy() -> None:
    text = _login_text()

    sign_in_index = text.find("Sign In")
    actions_index = text.find('id="login-commercial-actions"')

    assert sign_in_index >= 0
    assert actions_index > sign_in_index


def test_login_gateway_mobile_layout_can_stack_actions() -> None:
    text = _login_text()

    assert "@media (max-width: 520px)" in text
    assert "grid-template-columns: 1fr" in text


def test_login_gateway_does_not_expose_secret_markers() -> None:
    text = _login_text().lower()

    assert "provider_secret" not in text
    assert "encrypted_key" not in text
    assert "api_key" not in text
    assert "webhook_secret" not in text
