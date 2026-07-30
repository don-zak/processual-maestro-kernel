from pathlib import Path

LOGIN_HTML = Path("processual_api/static/login.html")
PRICING_HTML = Path("processual_api/static/pricing.html")
PLAN_DETAIL_HTML = Path("processual_api/static/plan_detail.html")


def test_pricing_surface_fetches_public_catalog() -> None:
    text = PRICING_HTML.read_text(encoding="utf-8")
    assert 'loadJson("/billing/commercial-pricing-catalog")' in text
    assert 'loadJson("/billing/pricing-catalog")' in text
    assert 'id="pricing-plan-grid"' in text
    assert "commercially_listed" in text


def test_pricing_index_does_not_display_internal_runtime_statuses() -> None:
    text = PRICING_HTML.read_text(encoding="utf-8")
    assert "Draft pricing" not in text
    assert "Checkout" not in text
    assert "Disabled" not in text
    assert "Unavailable" not in text


def test_plan_detail_discloses_byok_and_non_activation_boundaries() -> None:
    text = PLAN_DETAIL_HTML.read_text(encoding="utf-8")
    assert "BYOK only" in text
    assert "AI provider usage is outside the Maestro subscription" in text
    assert "Selection does not activate payment, subscription, quota enforcement, or entitlement grants" in text


def test_plan_surfaces_have_no_checkout_or_provider_links() -> None:
    text = (PRICING_HTML.read_text(encoding="utf-8") + PLAN_DETAIL_HTML.read_text(encoding="utf-8")).lower()
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text
    assert "lemonsqueezy" not in text
    assert "lemon_squeezy" not in text


def test_pricing_surfaces_do_not_expose_secret_markers() -> None:
    text = (PRICING_HTML.read_text(encoding="utf-8") + PLAN_DETAIL_HTML.read_text(encoding="utf-8")).lower()
    for marker in ("provider_secret", "encrypted_key", "api_key", "webhook_secret", "lemonsqueezy_api_key"):
        assert marker not in text


def test_login_commercial_panel_links_to_pricing_surface_without_checkout() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8").lower()
    assert 'href="/pricing"' in text
    assert 'aria-label="request access"' in text
    assert "/billing/checkout" not in text


def test_login_offers_action_links_directly_to_public_pricing_page() -> None:
    text = LOGIN_HTML.read_text(encoding="utf-8")
    assert 'id="login-offers-registration-button"' in text
    assert 'href="/pricing"' in text
    assert 'aria-label="View subscription options and registration"' in text
