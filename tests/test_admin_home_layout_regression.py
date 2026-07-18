
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_home_layout_after_fixups():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_home_layout.js" in html

    if "admin_runtime_fixups.js" in html:
        assert html.index("admin_runtime_fixups.js") < html.index("admin_home_layout.js")


def test_admin_home_layout_moves_runtime_cards_to_surface():
    script = (STATIC_DIR / "js" / "admin_home_layout.js").read_text(encoding="utf-8")

    required = [
        "admin-home-runtime-surface",
        "moveHomeRuntimeCards",
        "admin-runtime-home-summary",
        "admin-runtime-auth-state",
        "findOverviewAnchor",
        "position:static!important",
        "max-height:560px",
        "overflow:auto",
        "PMK_ADMIN_HOME_LAYOUT",
    ]

    for token in required:
        assert token in script


def test_admin_runtime_auth_checks_support_headers_objects():
    script = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")

    required = [
        "function hasHeader(headers, name)",
        "typeof headers.has === 'function'",
        "hasAuthTransport(headers)",
        "hasHeader(authHeaders(), 'Authorization')",
        "hasHeader(authHeaders(), 'X-API-Key')",
    ]

    for token in required:
        assert token in script
