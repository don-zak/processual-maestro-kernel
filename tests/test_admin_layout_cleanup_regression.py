
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_layout_cleanup_after_runtime():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_layout_cleanup.js" in html
    assert html.index("admin_runtime.js") < html.index("admin_layout_cleanup.js")


def test_admin_layout_cleanup_prunes_legacy_placeholders_and_scrolls_cards():
    script = (STATIC_DIR / "js" / "admin_layout_cleanup.js").read_text(encoding="utf-8")

    required = [
        "pruneLegacyPlaceholders",
        "Checking admin session",
        "Planned usage view",
        "System-level provider settings",
        "max-height:440px",
        "overflow:auto",
        "PMK_ADMIN_LAYOUT",
    ]

    for token in required:
        assert token in script


def test_admin_session_uses_auth_bridge_headers():
    script = (STATIC_DIR / "js" / "admin_session.js").read_text(encoding="utf-8")

    required = [
        "PMK_ADMIN_AUTH.headers",
        "fetch('/auth/me'",
        "Admin auth token missing",
        "Admin session verified",
        "Backend scopes remain the authority",
    ]

    for token in required:
        assert token in script
