from pathlib import Path

PRICING_HTML = Path("processual_api/static/pricing.html")
PLAN_DETAIL_HTML = Path("processual_api/static/plan_detail.html")


def test_pricing_surface_fetches_public_plan_catalog_only() -> None:
    source = PRICING_HTML.read_text(encoding="utf-8")
    assert 'loadJson("/billing/commercial-pricing-catalog")' in source
    assert 'loadJson("/billing/pricing-catalog")' in source
    assert 'id="pricing-plan-grid"' in source
    assert 'loadJson("/billing/offer-pricebook")' not in source


def test_pricing_surface_is_a_concise_plan_discovery_index() -> None:
    source = PRICING_HTML.read_text(encoding="utf-8")
    assert "Choose the plan that fits your work" in source
    assert "Discover this plan" in source
    assert "Draft offers" not in source
    assert "Pricing pending review" not in source
    assert "offer-pricebook" not in source
    assert "amount_cents" not in source


def test_commercial_details_are_in_dedicated_plan_space() -> None:
    source = PLAN_DETAIL_HTML.read_text(encoding="utf-8")
    for marker in (
        'id="monthly-price"',
        'id="annual-price"',
        'id="monthly-units"',
        'id="overage-price"',
        'id="feature-list"',
        "Commercial policies",
    ):
        assert marker in source


def test_new_surfaces_are_secret_safe_and_only_create_journey_context() -> None:
    source = (PRICING_HTML.read_text(encoding="utf-8") + PLAN_DETAIL_HTML.read_text(encoding="utf-8")).lower()

    for marker in (
        "provider_secret",
        "encrypted_key",
        "api_key",
        "webhook_secret",
        "lemonsqueezy",
        "lemon_squeezy",
        "/billing/checkout",
        "/billing/payment",
        "/billing/webhook",
        "/subscriptions",
        "/entitlements",
    ):
        assert marker not in source

    assert 'fetch("/registration/intents"' in source
    assert 'method: "post"' in source


def test_plan_confirmation_creates_and_preserves_registration_context() -> None:
    source = PLAN_DETAIL_HTML.read_text(encoding="utf-8")
    compact = "".join(source.split())

    assert 'fetch("/registration/intents"' in compact
    assert 'method:"POST"' in compact
    assert 'newURL("/register",window.location.origin)' in compact
    assert 'target.searchParams.set("plan",planId)' in compact
    assert 'target.searchParams.set("source","plan_detail")' in compact
    assert 'target.searchParams.set("journey_intent",intent.intent_id)' in compact
    assert 'sessionStorage.setItem("pmk.registrationJourney.intentId",intent.intent_id)' in compact
