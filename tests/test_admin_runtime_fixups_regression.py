from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_loads_runtime_fixups_after_layout_cleanup():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_runtime_fixups.js" in html
    assert html.index("admin_layout_cleanup.js") < html.index("admin_runtime_fixups.js")


def test_admin_fixups_cleanup_home_and_auth_card_only():
    script = (STATIC_DIR / "js" / "admin_runtime_fixups.js").read_text(encoding="utf-8")

    required = [
        "pruneAdminHome",
        "admin-runtime-home-summary",
        "admin-runtime-auth-state",
        "refreshAuthCard",
        "authHeaders.has('Authorization')",
        "PMK_ADMIN_RUNTIME_FIXUPS",
    ]
    for token in required:
        assert token in script


def test_admin_fixups_do_not_own_api_key_lifecycle_or_generation():
    script = (STATIC_DIR / "js" / "admin_runtime_fixups.js").read_text(encoding="utf-8")

    forbidden = [
        "external_evaluation",
        "admin-api-key-category",
        "admin-api-key-profile-controls",
        "generateProfiledApiKey",
        "request('POST', '/settings/api-keys'",
        "pmk-api-key-category-changed",
        "evaluationModeDisabled",
        "MutationObserver",
    ]
    for token in forbidden:
        assert token not in script
