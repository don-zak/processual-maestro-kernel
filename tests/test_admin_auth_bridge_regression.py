
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_auth_bridge_before_runtime():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_auth_bridge.js" in html
    assert html.index("admin_auth_bridge.js") < html.index("admin_runtime.js")


def test_admin_auth_bridge_scans_common_token_shapes_and_patches_fetch():
    script = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    required = [
        "accessToken",
        "authToken",
        "adminAccessToken",
        "processualSession",
        "localStorage",
        "sessionStorage",
        "Authorization",
        "X-API-Key",
        "diagnostic",
        "installFetchBridge",
        "bridgedFetch",
        "PMK_ADMIN_AUTH",
    ]

    for token in required:
        assert token in script
