from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_JS = ROOT / "processual_api" / "static" / "js" / "admin_marketplace_catalog.js"
ADMIN_ACTIONS_JS = ROOT / "processual_api" / "static" / "js" / "admin_actions.js"
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"


def test_catalog_ui_is_loaded_by_admin_shell() -> None:
    actions = ADMIN_ACTIONS_JS.read_text(encoding="utf-8")

    assert "admin_marketplace_catalog.js?v=a3-original-offers-1" in actions
    assert "loadAdminMarketplaceCatalog" in actions
    assert "data-admin-marketplace-catalog" in actions


def test_catalog_ui_replaces_the_reserved_catalog_panel() -> None:
    catalog = CATALOG_JS.read_text(encoding="utf-8")
    admin_html = ADMIN_HTML.read_text(encoding="utf-8")

    assert 'data-am-panel="catalog"' in admin_html
    assert "Commercial catalog workspace" in admin_html
    assert "installMarkup(panel)" in catalog
    assert "Canonical program catalog" in catalog
    assert "/admin-marketplace/catalog/offers" in catalog
    assert "am-catalog-offer-list" in catalog


def test_catalog_ui_keeps_local_payment_fail_closed() -> None:
    catalog = CATALOG_JS.read_text(encoding="utf-8")

    assert "local_payment_ready" in catalog
    assert "local_payment_gate_reasons" in catalog
    assert "Local payment blocked" in catalog
    assert "confirmed Tunisian address" in catalog
    assert "active default destination" in catalog
    assert "offer_not_published" in catalog
    assert "price_not_approved" in catalog
    assert "currency_not_tnd" in catalog
    assert "checkout_disabled" in catalog


def test_payment_destination_validate_remains_separate_from_activation() -> None:
    admin_html = ADMIN_HTML.read_text(encoding="utf-8")
    marketplace_js = (
        ROOT / "processual_api" / "static" / "js" / "admin_marketplace.js"
    ).read_text(encoding="utf-8")

    assert "It never activates or sets the destination as default." in admin_html
    assert "if (item.status === 'draft') actions.push(['validate', 'Validate']);" in marketplace_js
    assert "if (item.status === 'validated') actions.push(['activate', 'Activate']);" in marketplace_js
    assert "if (item.status === 'active' && !item.is_default)" in marketplace_js
