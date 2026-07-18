from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_does_not_load_console_auth_script():
    html = read_static("admin.html")

    forbidden = [
        'js/auth.js',
        '/console/js/auth.js',
        'AUTH.init()',
    ]

    for token in forbidden:
        assert token not in html

    required = [
        'js/admin_session.js',
        'js/admin_nav.js',
    ]

    for token in required:
        assert token in html


def test_admin_session_never_redirects_to_splash_page():
    script = (STATIC_DIR / "js" / "admin_session.js").read_text(encoding="utf-8")

    assert "window.location.replace('/')" not in script
    assert "window.location.href = '/'" not in script
    assert "Admin auth token missing" in script
    assert "PMK_ADMIN_AUTH.headers" in script

def test_admin_navigation_binds_buttons_and_switches_pages():
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
