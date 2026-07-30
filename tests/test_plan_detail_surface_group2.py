from pathlib import Path

PRICING = Path("processual_api/static/pricing.html")
DETAIL = Path("processual_api/static/plan_detail.html")


def test_pricing_is_a_concise_available_plan_index() -> None:
    text = PRICING.read_text(encoding="utf-8")
    assert 'href="/plans/${id}"' in text
    assert "Discover this plan" in text
    assert "price-label" not in text
    assert "offer-pricebook" not in text
    assert "Checkout</span>" not in text
    assert "Unavailable" not in text


def test_plan_detail_uses_authoritative_single_plan_api() -> None:
    text = DETAIL.read_text(encoding="utf-8")
    assert "/billing/commercial-pricing-catalog/${encodeURIComponent(planId)}" in text
    assert 'id="monthly-price"' in text
    assert 'id="annual-price"' in text
    assert 'id="monthly-units"' in text
    assert 'id="confirm-plan"' in text


def test_opening_plan_detail_only_creates_registration_journey_context() -> None:
    text = DETAIL.read_text(encoding="utf-8")

    assert 'fetch("/registration/intents"' in text
    assert 'method: "POST"' in text
    assert "/billing/checkout" not in text
    assert "/billing/payment" not in text
    assert "/billing/webhook" not in text
    assert "/subscriptions" not in text
    assert "/entitlements" not in text


def test_plan_confirmation_preserves_plan_context_for_registration() -> None:
    text = DETAIL.read_text(encoding="utf-8")
    compact = "".join(text.split())

    assert 'newURL("/register",window.location.origin)' in compact
    assert 'target.searchParams.set("plan",planId)' in compact
    assert 'target.searchParams.set("source","plan_detail")' in compact
    assert 'target.searchParams.set("journey_intent",intent.intent_id)' in compact
    assert 'sessionStorage.setItem("pmk.registrationJourney.intentId",intent.intent_id)' in compact


def test_new_surfaces_do_not_contain_mojibake() -> None:
    combined = PRICING.read_text(encoding="utf-8") + DETAIL.read_text(encoding="utf-8")
    assert "Ãƒ" not in combined
    assert "Ã‚" not in combined
    assert "Ã¢â‚¬" not in combined
