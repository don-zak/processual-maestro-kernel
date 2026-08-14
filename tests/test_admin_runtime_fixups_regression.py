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


def test_admin_fixups_add_standard_api_key_profile_controls_only_for_standard_categories():
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
        "controls.dataset.standardApiKeyOnly = 'true'",
        "removeApiKeyProfileControls",
    ]

    for token in required:
        assert token in script


def test_admin_fixups_hard_block_standard_generation_for_external_evaluation():
    script = (STATIC_DIR / "js" / "admin_runtime_fixups.js").read_text(encoding="utf-8")

    required = [
        "const EXTERNAL_CATEGORY = 'external_evaluation'",
        "function externalEvaluationSelected()",
        "document.getElementById('admin-api-key-category')?.value === EXTERNAL_CATEGORY",
        "if (externalEvaluationSelected())",
        "removeApiKeyProfileControls();",
        "Standard API key generation is blocked for External Evaluation.",
        "Complete the Evaluation Grant lifecycle and use Issue API Key",
        "generateButton.dataset.evaluationModeDisabled = 'true'",
        "window.addEventListener('pmk-api-key-category-changed'",
    ]
    for token in required:
        assert token in script

    generation_start = script.index("async function generateProfiledApiKey()")
    profile_start = script.index("const profileName", generation_start)
    guard = script[generation_start:profile_start]
    assert "return;" in guard
    assert "request('POST', '/settings/api-keys'" not in guard
