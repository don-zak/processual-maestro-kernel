from pathlib import Path

STATIC_DIR = Path("processual_api/static")


def test_public_pages_embed_favicon_data_uri() -> None:
    pages = [
        STATIC_DIR / "pricing.html",
        STATIC_DIR / "index.html",
        STATIC_DIR / "login.html",
        STATIC_DIR / "admin.html",
    ]

    existing_pages = [page for page in pages if page.exists()]
    assert existing_pages

    for page in existing_pages:
        source = page.read_text(encoding="utf-8")
        assert '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,' in source
        assert "/static/favicon.svg" not in source
        assert "/favicon.ico" not in source


def test_pricing_page_does_not_trigger_network_favicon_lookup() -> None:
    source = (STATIC_DIR / "pricing.html").read_text(encoding="utf-8")

    assert "data:image/svg+xml;base64," in source
    assert "/static/favicon.svg" not in source
    assert "/favicon.ico" not in source
    assert "shortcut icon" not in source.lower()


def test_static_favicon_file_is_not_required_for_public_pages() -> None:
    assert not (STATIC_DIR / "favicon.svg").exists()
