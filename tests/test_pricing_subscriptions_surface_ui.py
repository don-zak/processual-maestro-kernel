from pathlib import Path

LOGIN_HTML = Path("processual_api/static/login.html")
PRICING_HTML = Path("processual_api/static/pricing.html")


def _pricing_text() -> str:
    return PRICING_HTML.read_text(encoding="utf-8")


def test_pricing_surface_file_exists_and_fetches_public_catalog() -> None:
    text = _pricing_text()

    assert PRICING_HTML.exists()
    assert "Subscription options" in text
    assert 'loadJson("/billing/pricing-catalog")' in text
    assert 'id="pricing-plan-grid"' in text
    assert "commercially_listed" in text


def test_pricing_surface_renders_catalog_safety_metadata() -> None:
    text = _pricing_text()

    assert "Draft pricing" in text
    assert "BYOK" in text
    assert "provider costs are not included" in text.lower()
    assert "Checkout" in text
    assert "Disabled" in text


def test_pricing_surface_has_request_access_but_no_checkout_link() -> None:
    text = _pricing_text().lower()

    assert 'href="/apply"' in text
    assert "request access" in text
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text
    assert "lemonsqueezy" not in text
    assert "lemon_squeezy" not in text


def test_pricing_surface_does_not_expose_secret_markers() -> None:
    text = _pricing_text().lower()

    assert "provider_secret" not in text
    assert "encrypted_key" not in text
    assert "api_key" not in text
    assert "webhook_secret" not in text
    assert "lemonsqueezy_api_key" not in text


def test_login_commercial_panel_links_to_pricing_surface_without_checkout() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8").lower()

    assert 'href="/pricing"' in text
    assert 'aria-label="request access"' in text
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text

def test_login_offers_action_links_directly_to_public_pricing_page() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")

    assert 'id="login-offers-registration-button"' in text
    assert 'href="/pricing"' in text
    assert 'aria-label="View subscription options and registration"' in text
