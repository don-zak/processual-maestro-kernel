from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_loads_navigation_script():
    html = read_static("admin.html")
    assert "js/admin_nav.js" in html


def test_admin_sidebar_contains_productized_admin_targets():
    html = read_static("admin.html")

    required = [
        'data-admin-page="home"',
        'data-admin-page="adapters"',
        'data-admin-page="api-keys"',
        'data-admin-page="clients"',
        'data-admin-page="usage"',
        'data-admin-page="program-progress"',
        'data-admin-page="system-health"',
        'data-admin-page="system-settings"',
    ]

    for token in required:
        assert token in html


def test_admin_nav_script_switches_runtime_pages():
    script = (STATIC_DIR / "js" / "admin_nav.js").read_text(encoding="utf-8")

    required = [
        "setActivePage",
        "pageFromButton",
        "event.preventDefault()",
        "event.stopImmediatePropagation()",
        "page-admin-home",
        "page-admin-adapters",
        "page-admin-api-keys",
        "page-admin-clients",
        "page-admin-usage",
        "page-admin-program-progress",
        "page-admin-system-health",
        "page-admin-system-settings",
        "window.PMK_ADMIN_NAV",
    ]

    for token in required:
        assert token in script
