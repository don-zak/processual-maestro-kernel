from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_auth_bridge_before_runtime() -> None:
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_auth_bridge.js" in html
    assert html.index("admin_auth_bridge.js") < html.index("admin_runtime.js")


def test_admin_auth_bridge_uses_canonical_identity_session_and_patches_fetch() -> None:
    script = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    required = [
        "const IDENTITY_TOKEN_KEY = 'maestro_token'",
        "const SUPERVISOR_SESSION_KEY = 'pmk_supervisor_session_key'",
        "sessionStorage",
        "Authorization",
        "X-API-Key",
        "X-Supervisor-Session-Key",
        "diagnostic",
        "clearIdentitySession",
        "purgeLegacyCredentialStorage",
        "installFetchBridge",
        "PMK_ADMIN_AUTH",
    ]
    for token in required:
        assert token in script

    assert "localStorage.getItem" not in script
    assert "scanStorage" not in script
    assert "preferredKeys" not in script
    assert "legacyStorageScanEnabled: false" in script
    assert "localStorageUsedForAuth: false" in script
