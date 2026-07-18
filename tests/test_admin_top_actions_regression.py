from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_top_buttons_are_real_navigation_controls():
    html = read_static("admin.html")

    required = [
        'id="admin-client-console-btn"',
        'href="/console"',
        'id="admin-logout-btn"',
        'href="/login?mode=admin"',
        'id="admin-top-actions-fallback"',
        "PMK_ADMIN_TOP_ACTIONS_INLINE",
        "js/admin_actions.js",
    ]

    for token in required:
        assert token in html


def test_admin_actions_script_binds_client_console_and_logout():
    script = (STATIC_DIR / "js" / "admin_actions.js").read_text(encoding="utf-8")

    required = [
        "openClientConsole",
        "window.location.assign('/console')",
        "logout",
        "CLIENT.post('/auth/logout'",
        "clearAuthState",
        "window.location.replace('/login?mode=admin')",
        "PMK_ADMIN_ACTIONS",
    ]

    for token in required:
        assert token in script
