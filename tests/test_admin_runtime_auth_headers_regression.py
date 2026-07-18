from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_runtime_uses_auth_bridge_for_backend_headers():
    runtime = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")
    bridge = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    runtime_required = [
        "PMK_ADMIN_AUTH.headers",
        "credentials: 'include'",
        "fetch(path",
        "Admin Auth Transport",
        "Bearer token found",
    ]

    for token in runtime_required:
        assert token in runtime

    bridge_required = [
        "function headers(",
        "Authorization",
        "X-API-Key",
        "diagnostic",
        "installFetchBridge",
        "PMK_ADMIN_AUTH",
    ]

    for token in bridge_required:
        assert token in bridge


def test_admin_cards_are_scrollable_for_long_backend_output():
    cleanup = (STATIC_DIR / "js" / "admin_layout_cleanup.js").read_text(encoding="utf-8")

    required = [
        "max-height:440px",
        "overflow:auto",
        "#admin-api-key-create-result,#admin-api-key-list",
    ]

    for token in required:
        assert token in cleanup
