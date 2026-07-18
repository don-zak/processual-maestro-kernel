from pathlib import Path

PRICING_HTML = Path("processual_api/static/pricing.html")


def _pricing_text() -> str:
    return PRICING_HTML.read_text(encoding="utf-8")


def _context_around(source: str, marker: str, before: int = 300, after: int = 300) -> str:
    index = source.index(marker)
    return source[max(index - before, 0) : index + after]


def test_pricing_factors_card_is_hidden_under_offers_and_toggle_controlled() -> None:
    source = _pricing_text()

    assert 'id="pricing-factors-toggle"' in source
    assert 'id="pricing-factors-card"' in source
    assert "pmkPricingFactorsToggleController" in source
    assert "public pricing factors are hidden until opened" in source
    assert ".pricing-factors-card{" in source
    assert "display:none!important" in source
    assert ".pricing-factors-card.is-open{" in source
    assert "display:block!important" in source
    assert 'setPricingFactorsOpen(card, button, false)' in source
    assert 'event.stopImmediatePropagation()' in source
    assert 'button.setAttribute("aria-expanded", isOpen ? "true" : "false")' in source
    assert 'card.setAttribute("aria-hidden", isOpen ? "false" : "true")' in source


def test_pricing_factors_card_uses_public_assumptions_route_without_internal_values() -> None:
    source = _pricing_text()

    assert 'fetch("/billing/unit-cost-assumptions"' in source
    assert "loadPublicPricingFactors" in source
    assert "review_status" in source
    assert "billing_policy" in source
    assert "provider_cost_included" in source
    assert "approved_for_checkout" in source

    card_start = source.index('id="pricing-factors-card"')
    card_end = source.index("</article>", card_start)
    card_markup = source[card_start:card_end]

    assert "amount_cents" not in card_markup


def test_pricing_factors_card_is_language_scoped() -> None:
    source = _pricing_text()

    assert 'data-label-ar="عوامل التسعير"' in source
    assert 'data-label-en="Pricing factors under review"' in source
    assert 'data-pricing-factors-lang="ar"' in source
    assert 'data-pricing-factors-lang="en"' in source
    assert 'lang="ar" dir="rtl" hidden' in source
    assert 'lang="en" hidden' in source
    assert "currentPricingFactorsLanguage" in source
    assert "document.documentElement.getAttribute" in source
    assert "section.hidden = !isActive" in source


def test_pricing_factors_card_does_not_publish_internal_cost_or_profit_model() -> None:
    source = _pricing_text().lower()

    forbidden_markers = (
        "target_margin",
        "minimum_price_cents",
        "recommended_price_cents",
        "risk_buffer_cents",
        "local_tax_reserve_cents",
        "processor_percent",
        "processor_fixed_fee_cents",
        "server_or_cloud_run_cost_cents",
        "database_cost_cents",
        "cache_cost_cents",
        "storage_cost_cents",
        "egress_cost_cents",
    )

    for marker in forbidden_markers:
        assert marker not in source


def test_pricing_bottom_actions_use_one_shape_with_task_colors() -> None:
    source = _pricing_text()

    assert "PRICING-COST-08G-R1: unified bottom actions" in source
    assert ".pricing-bottom-action{" in source
    assert "border-radius:999px" in source
    assert "min-height:48px" in source

    assert 'id="pricing-factors-toggle"' in source
    assert 'id="pricing-refund-terms-toggle"' in source
    assert 'href="/apply"' in source
    assert 'href="/login"' in source

    assert "pricing-bottom-action--info" in _context_around(source, 'id="pricing-factors-toggle"')
    assert "pricing-bottom-action--policy" in _context_around(source, 'id="pricing-refund-terms-toggle"')
    assert "pricing-bottom-action--primary" in _context_around(source, "Request access")
    assert "pricing-bottom-action--secondary" in _context_around(source, "Return to login")

    assert '"cta"' not in source
    assert '"cta secondary"' not in source
    assert 'class=" pricing-bottom-action' not in source
