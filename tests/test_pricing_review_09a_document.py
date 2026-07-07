from pathlib import Path

DOC = Path("docs/pricing/PRICING_REVIEW_09A_DRAFT.md")


def test_pricing_review_09a_document_exists_and_is_internal_draft() -> None:
    source = DOC.read_text(encoding="utf-8")

    assert "PRICING-REVIEW-09A" in source
    assert "Status: `draft_review`" in source
    assert "Public pricing approved: `false`" in source
    assert "Checkout approved: `false`" in source
    assert "Lemon Squeezy wiring approved: `false`" in source
    assert "Currency approved: `false`" in source


def test_pricing_review_09a_has_consultation_price_ranges_not_public_prices() -> None:
    source = DOC.read_text(encoding="utf-8")

    assert "Draft price list for consultation" in source
    assert "Pilot Starter" in source
    assert "Pilot Pro" in source
    assert "Institution Trial" in source
    assert "Enterprise Private" in source
    assert "These are review candidates, not approved prices." in source


def test_pricing_review_09a_keeps_checkout_and_profit_details_private() -> None:
    source = DOC.read_text(encoding="utf-8")
    lower_source = source.lower()

    assert "do not wire checkout" in lower_source
    assert "do not publish final prices" in lower_source
    assert "byok applies" in lower_source
    assert "ai provider costs are not included" in lower_source

    public_start = source.index("Allowed public wording:")
    public_end = source.index("Not allowed in public wording:")
    allowed_public_wording = source[public_start:public_end].lower()

    forbidden_public_markers = (
        "approved checkout=true",
        "lemon variant id",
        "target_margin",
        "profit margin targets",
        "risk buffer amounts",
        "server or database cost values",
    )

    for marker in forbidden_public_markers:
        assert marker not in allowed_public_wording
