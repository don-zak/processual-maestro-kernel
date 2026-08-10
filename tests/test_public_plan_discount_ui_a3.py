from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "plans.js"
OFFER_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "offer.js"


def test_plan_cards_render_discount_from_catalog_payload() -> None:
    source = PLANS_JS.read_text(encoding="utf-8")

    assert "annual_discount_percent" in source
    assert "discountPercent(plan)" in source
    assert "save ${discount}%" in source
    assert "save 20%" not in source.lower()
    assert "save 15%" not in source.lower()


def test_offer_page_renders_discount_from_catalog_payload() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "annual_discount_percent" in source
    assert "discountPercent(plan)" in source
    assert "Save ${annualDiscount}% on the base annual plan." in source
    assert "save 20%" not in source.lower()
    assert "save 15%" not in source.lower()


def test_offer_add_ons_explicitly_exclude_annual_base_discount() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "Annual subscription discount does not apply." in source
