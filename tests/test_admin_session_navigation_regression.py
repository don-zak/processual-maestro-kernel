from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_does_not_load_console_auth_script() -> None:
    html = read_static("admin.html")

    for token in ('js/auth.js', '/console/js/auth.js', 'AUTH.init()'):
        assert token not in html
    for token in ('js/admin_session.js', 'js/admin_nav.js'):
        assert token in html


def test_admin_session_never_redirects_to_splash_and_fails_closed() -> None:
    script = (STATIC_DIR / "js" / "admin_session.js").read_text(encoding="utf-8")

    assert "window.location.replace('/')" not in script
    assert "window.location.href = '/'" not in script
    assert "Active administrator Identity session required" in script
    assert "AUTHORITY_ENDPOINT" in script
    assert "clearIdentitySession" in script
    assert "Protected controls are locked" in script


def test_admin_navigation_binds_buttons_and_switches_pages() -> None:
    script = (STATIC_DIR / "js" / "admin_nav.js").read_text(encoding="utf-8")

    required = [
        "bindNavButtons",
        "labelToPage",
        "setActivePage",
        "event.preventDefault()",
        "event.stopPropagation()",
        "page-admin-home",
        "page-admin-adapters",
        "page-admin-api-keys",
        "page-admin-system-settings",
        "window.PMK_ADMIN_NAV",
    ]
    for token in required:
        assert token in script
