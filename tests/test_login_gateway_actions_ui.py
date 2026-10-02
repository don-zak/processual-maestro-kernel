from pathlib import Path
import re

LOGIN_HTML = Path("processual_api/static/login.html")
ARABIC = re.compile(r"[\u0600-\u06ff]")


def _login_text() -> str:
    return LOGIN_HTML.read_text(encoding="utf-8")


def test_login_gateway_commercial_and_recovery_actions_exist() -> None:
    text = _login_text()

    assert 'id="login-commercial-actions"' in text
    assert 'id="login-offers-registration-button"' in text
    assert 'id="login-lost-access-button"' in text
    assert "Offers &amp; Registration" in text
    assert "Lost Access?" in text
    assert 'href="/plans"' in text
    assert 'href="/console/account-recovery.html"' in text


def test_login_gateway_is_english_only() -> None:
    text = _login_text()

    assert '<html lang="en" dir="ltr">' in text
    assert "data-ar" not in text
    assert 'data-lang="ar"' not in text
    assert ARABIC.search(text) is None


def test_login_gateway_actions_are_secondary_navigation_not_checkout_links() -> None:
    text = _login_text().lower()

    assert 'id="login-commercial-actions"' in text
    assert 'href="/plans"' in text
    assert 'href="/console/account-recovery.html"' in text
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text
    assert "lemonsqueezy" not in text
    assert "lemon_squeezy" not in text


def test_login_gateway_recovery_navigation_does_not_duplicate_recovery_authority() -> None:
    text = _login_text().lower()

    assert 'href="/console/account-recovery.html"' in text
    assert "contact your administrator or support contact" not in text
    assert "temporary password" not in text


def test_login_gateway_keeps_admin_user_entry_modes() -> None:
    text = _login_text()

    assert 'id="tab-admin"' in text
    assert 'id="tab-user"' in text
    assert "Admin" in text
    assert "User" in text
    assert "maestro_entry_mode" in text


def test_login_gateway_preserves_request_access_link() -> None:
    text = _login_text()

    assert 'href="/apply"' in text
    assert 'aria-label="Request access"' in text
    assert "Request Access" in text


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
