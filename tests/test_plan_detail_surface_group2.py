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


def test_opening_plan_detail_does_not_create_commercial_mutations() -> None:
    text = DETAIL.read_text(encoding="utf-8")
    assert 'method: "POST"' not in text
    assert "/billing/checkout" not in text
    assert "/registration/intents" not in text
    assert "/billing/payment" not in text


def test_plan_confirmation_preserves_plan_context_for_registration() -> None:
    text = DETAIL.read_text(encoding="utf-8")
    assert 'new URL("/register",window.location.origin)' in text
    assert 'target.searchParams.set("plan",planId)' in text
    assert 'target.searchParams.set("source","plan_detail")' in text


def test_new_surfaces_do_not_contain_mojibake() -> None:
    combined = PRICING.read_text(encoding="utf-8") + DETAIL.read_text(encoding="utf-8")
    assert "Ãƒ" not in combined
    assert "Ã‚" not in combined
    assert "Ã¢â‚¬" not in combined
