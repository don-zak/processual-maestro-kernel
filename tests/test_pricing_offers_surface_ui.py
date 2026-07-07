from pathlib import Path

PRICING_HTML = Path("processual_api/static/pricing.html")


def _pricing_text() -> str:
    return PRICING_HTML.read_text(encoding="utf-8")


def test_pricing_surface_fetches_offer_pricebook() -> None:
    text = _pricing_text()

    assert 'loadJson("/billing/offer-pricebook")' in text
    assert 'id="pricing-offers-section"' in text
    assert 'id="pricing-offer-grid"' in text
    assert 'id="offer-pricebook-state"' in text


def test_pricing_surface_renders_draft_offer_review_language() -> None:
    text = _pricing_text()

    assert "Draft offers" in text
    assert "Offer structures under review" in text
    assert "Pricing pending review" in text
    assert "Calculation method" in text
    assert "Pending review" in text


def test_pricing_surface_offer_metadata_has_no_final_amounts_or_checkout() -> None:
    text = _pricing_text().lower()

    assert "amount_cents" in text
    assert "pending review" in text
    assert "/billing/checkout" not in text
    assert "billing/checkout" not in text
    assert "checkout enabled" not in text


def test_pricing_surface_offer_metadata_is_secret_safe() -> None:
    text = _pricing_text().lower()

    assert "provider_secret" not in text
    assert "encrypted_key" not in text
    assert "api_key" not in text
    assert "webhook_secret" not in text
    assert "lemonsqueezy" not in text
    assert "lemon_squeezy" not in text


def test_pricing_surface_has_bilingual_refund_terms_card() -> None:
    source = Path("processual_api/static/pricing.html").read_text(encoding="utf-8")

    assert 'id="pricing-refund-terms-toggle"' in source
    assert "شروط الاسترجاع / Refund terms" in source
    assert 'id="pricing-refund-terms-card"' in source
    assert "تُراجع طلبات الاسترجاع" in source
    assert "Refund requests are reviewed" in source
    assert "program runs" in source
    assert "تنفيذ المهام" in source
    assert "external agents" in source
    assert "وكلائه أو مزوديه" in source
    assert "aria-expanded" in source
    assert "aria-hidden" in source


def test_pricing_surface_renders_fulfillment_policy_labels() -> None:
    source = Path("processual_api/static/pricing.html").read_text(encoding="utf-8")

    assert "fulfillmentLabel" in source
    assert "Paid trial · no supervisor approval required" in source
    assert "Enterprise review required before custom pricing" in source
    assert "Self-service after registration and payment" in source
