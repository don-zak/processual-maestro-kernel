from pathlib import Path

LOGIN = Path("processual_api/static/login.html")
REGISTER = Path("processual_api/static/register.html")
PRICING = Path("processual_api/static/pricing.html")
AUTH_JS = Path("processual_api/static/js/auth_commercial_alignment_group2.js")


def test_login_loads_alignment_assets() -> None:
    text = LOGIN.read_text(encoding="utf-8")

    assert "/static/css/auth_commercial_alignment_group2.css" in text
    assert "/static/js/auth_commercial_alignment_group2.js" in text


def test_password_visibility_is_accessible() -> None:
    text = AUTH_JS.read_text(encoding="utf-8")

    assert "aria-pressed" in text
    assert "Show password" in text
    assert "Hide password" in text
    assert "setSelectionRange" in text
    assert 'button.type = "button"' in text


def test_login_separates_registration_from_pricing() -> None:
    text = AUTH_JS.read_text(encoding="utf-8")

    assert "/register.html" in text
    assert "Create account" in text
    assert "/pricing" in text
    assert "View subscription plans" in text


def test_registration_page_uses_real_auth_endpoints() -> None:
    text = REGISTER.read_text(encoding="utf-8")

    assert "/auth/registration/config" in text
    assert "/auth/register" in text
    assert 'autocomplete="new-password"' in text
    assert 'role="alert"' in text
    assert 'role="status"' in text
    assert "terms_version" in text
    assert "organization_name" in text


def test_registration_is_separate_from_checkout() -> None:
    text = REGISTER.read_text(encoding="utf-8").lower()

    assert "/billing/checkout" not in text
    assert "lemonsqueezy" not in text
    assert "registration creates an identity only" in text


def test_pricing_responsive_selectors_are_correct() -> None:
    text = PRICING.read_text(encoding="utf-8")

    assert ".status-row,.plan-grid,.offer-grid" in text
    assert ".status-row,plan-grid,offer-grid" not in text
