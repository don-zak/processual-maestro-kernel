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
    assert 'data-label-ar="شروط الاسترجاع"' in source
    assert 'data-label-en="Refund terms"' in source
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


def test_pricing_refund_terms_are_language_scoped_not_simultaneous() -> None:
    source = Path("processual_api/static/pricing.html").read_text(encoding="utf-8")

    assert 'data-refund-lang="ar"' in source
    assert 'data-refund-lang="en"' in source
    assert 'lang="ar" dir="rtl" hidden' in source
    assert 'lang="en" hidden' in source
    assert "pmkRefundTermsLanguageScoped" in source
    assert "refundTermsLanguage" in source
    assert "syncRefundTermsLanguage" in source
    assert 'document.documentElement.getAttribute("lang")' in source
    assert "section.hidden = !isActive" in source
    assert "section.dataset.refundLang === activeLang" in source
    assert "refundTermsToggle.dataset.labelAr" in source
    assert "refundTermsToggle.dataset.labelEn" in source
    assert "refund-terms-grid" not in source
    assert "refund-terms-lang" not in source


def test_pricing_refund_terms_card_is_hidden_until_button_toggle() -> None:
    source = Path("processual_api/static/pricing.html").read_text(encoding="utf-8")

    assert "pmkRefundTermsToggleController" in source
    assert "refund terms are hidden until the button opens them" in source
    assert ".refund-terms-card{" in source
    assert "display:none!important" in source
    assert ".refund-terms-card.is-open{" in source
    assert "display:block!important" in source
    assert 'setRefundTermsOpen(card, button, false)' in source
    assert 'event.stopImmediatePropagation()' in source
    assert 'button.setAttribute("aria-expanded", isOpen ? "true" : "false")' in source
    assert 'card.setAttribute("aria-hidden", isOpen ? "false" : "true")' in source
    assert 'button.dataset.refundToggleController = "ready"' in source
