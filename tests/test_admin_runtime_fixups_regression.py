
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_runtime_fixups_after_layout_cleanup():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_runtime_fixups.js" in html
    assert html.index("admin_layout_cleanup.js") < html.index("admin_runtime_fixups.js")


def test_admin_fixups_cleanup_home_and_auth_card():
    script = (STATIC_DIR / "js" / "admin_runtime_fixups.js").read_text(encoding="utf-8")

    required = [
        "pruneAdminHome",
        "admin-runtime-home-summary",
        "admin-runtime-auth-state",
        "refreshAuthCard",
        "authHeaders.has('Authorization')",
        "PMK_ADMIN_RUNTIME_FIXUPS",
        "service_integration",
        "Service Integration",
        "Server-to-server integration access",
        "profiles.service_integration",
        "read:adapters",
        "read:governor",
        "run:govern",
        "purpose",
        "issued_to",
        "client_id",
        "user_id",
        "plan_id",
    ]

    for token in required:
        assert token in script


def test_admin_fixups_add_api_key_profile_controls():
    script = (STATIC_DIR / "js" / "admin_runtime_fixups.js").read_text(encoding="utf-8")

    required = [
        "admin-api-key-profile",
        "client_api",
        "pilot_client",
        "support_viewer",
        "ops_admin",
        "security_admin",
        "owner_admin",
        "generateProfiledApiKey",
        "requestedProfile",
        "category",
        "role",
        "scopes",
    ]

    for token in required:
        assert token in script
