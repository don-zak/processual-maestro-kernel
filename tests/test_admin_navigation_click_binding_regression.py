from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_nav_has_inline_click_fallback():
    html = read_static("admin.html")

    required = [
        'id="admin-nav-click-fallback"',
        "PMK_ADMIN_NAV_INLINE",
        "setActivePage",
        "button.onclick",
        "data-admin-page",
    ]

    for token in required:
        assert token in html


def test_admin_nav_script_directly_binds_button_onclick_handlers():
    script = (STATIC_DIR / "js" / "admin_nav.js").read_text(encoding="utf-8")

    required = [
        "button.onclick",
        "event.stopImmediatePropagation()",
        "setActivePage(page)",
        "window.PMK_ADMIN_NAV",
        "bindNavButtons",
        "labelToPage",
    ]

    for token in required:
        assert token in script
