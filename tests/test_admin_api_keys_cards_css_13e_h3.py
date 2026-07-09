from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
ADMIN_CSS = ROOT / "processual_api" / "static" / "css" / "admin_ui_hardening_13c.css"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_13e_h3_api_key_metadata_card_css_marker_and_scope() -> None:
    css = read(ADMIN_CSS)

    assert "13E-H3 API key metadata card readability" in css
    assert "#page-admin-api-keys .admin-api-key-metadata-card-list" in css
    assert "#page-admin-api-keys .admin-api-key-metadata-card" in css
    assert "#page-admin-api-keys .admin-api-key-metadata-card > summary" in css
    assert "#page-admin-api-keys .admin-api-key-metadata-card-grid" in css
    assert "#page-admin-api-keys .admin-api-key-metadata-card-row" in css


def test_13e_h3_admin_css_cache_is_bumped() -> None:
    html = read(ADMIN_HTML)

    assert "admin_ui_hardening_13c.css?v=adminui13c-13eh3r2toggle" in html


def test_13e_h3_does_not_remove_h2_api_key_script_cache_bump() -> None:
    html = read(ADMIN_HTML)

    assert "admin_api_keys.js?v=adminapikeys13eh2" in html


def test_13e_h3_r1_forces_metadata_cards_collapsed_by_default() -> None:
    css = read(ADMIN_CSS)
    html = read(ADMIN_HTML)

    assert "13E-H3-R1 force metadata cards collapsed by default" in css
    assert ".admin-api-key-metadata-card:not([open]) .admin-api-key-metadata-card-body" in css
    assert "display: none !important" in css
    assert ".admin-api-key-metadata-card[open] .admin-api-key-metadata-card-body" in css
    assert ".admin-api-key-metadata-card > summary::after" in css
    assert ".admin-api-key-metadata-card[open] > summary::after" in css
    assert "admin_ui_hardening_13c.css?v=adminui13c-13eh3r2toggle" in html


def test_13e_h3_r2_metadata_cards_have_visible_toggle_labels() -> None:
    source = read(ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js")
    css = read(ADMIN_CSS)
    html = read(ADMIN_HTML)

    assert "admin-api-key-metadata-card-summary" in source
    assert "admin-api-key-metadata-card-title" in source
    assert "admin-api-key-metadata-card-toggle" in source
    assert "admin-api-key-metadata-card-toggle-open" in source
    assert "admin-api-key-metadata-card-toggle-close" in source
    assert ">Open<" in source
    assert ">Close<" in source

    assert "13E-H3-R2 visible metadata card toggle" in css
    assert ".admin-api-key-metadata-card-summary" in css
    assert ".admin-api-key-metadata-card-toggle" in css
    assert ".admin-api-key-metadata-card-toggle-open" in css
    assert ".admin-api-key-metadata-card-toggle-close" in css
    assert ".admin-api-key-metadata-card:not([open]) .admin-api-key-metadata-card-body" in css
    assert "display: none !important" in css

    assert "admin_ui_hardening_13c.css?v=adminui13c-13eh3r2toggle" in html
