from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_API_KEYS_JS = ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js"
ADMIN_RUNTIME_FIXUPS_JS = ROOT / "processual_api" / "static" / "js" / "admin_runtime_fixups.js"
ADMIN_RUNTIME_JS = ROOT / "processual_api" / "static" / "js" / "admin_runtime.js"


def _combined_admin_api_key_sources() -> str:
    parts = []
    for path in [ADMIN_API_KEYS_JS, ADMIN_RUNTIME_FIXUPS_JS, ADMIN_RUNTIME_JS]:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_admin_api_key_ui_explains_external_programmatic_access():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "programmatic access",
        "outside the browser login",
        "X-API-Key",
        "not an authentication bypass",
        "governed",
    ]

    for phrase in required_phrases:
        assert phrase in source


def test_admin_api_key_ui_uses_operational_credential_guidance_not_marketing_copy():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "Credential safety",
        "least privilege",
        "explicit expiry",
        "revoke access",
        "raw API key is displayed once only",
        "backend scope, status, usage, and revocation records remain authoritative",
        "Platform Administrator Evaluation Grant authority",
        "fixed admitted-execution quota",
        "production disabled",
    ]
    for phrase in required_phrases:
        assert phrase in source

    forbidden_phrases = [
        "Tunisia introductory access positioning",
        "introductory access / pilot access",
        "practical onboarding path",
        "early spread and demos",
        "not the primary sales model",
        "Backward-compatible regression markers",
        "CLIENT.get('/settings/api-keys')",
        "CLIENT.post('/settings/api-keys'",
        "ADMIN-INTEGRATION-KEYS-11F pending bridge",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in source


def test_admin_api_key_ui_declares_required_profile_fields():
    source = _combined_admin_api_key_sources()

    required_fields = [
        "category",
        "role",
        "scopes",
        "plan_id",
        "quota_limit_override",
        "expires_at",
        "purpose",
        "issued_to",
    ]

    for field in required_fields:
        assert field in source


def test_admin_api_key_ui_declares_supported_key_categories():
    source = _combined_admin_api_key_sources()

    required_categories = [
        "client_api",
        "pilot_client",
        "external_partner",
        "service_integration",
        "billing_service",
        "support_viewer",
        "ops_admin",
        "billing_admin",
        "security_admin",
        "owner_admin",
        "emergency_bootstrap",
    ]

    for category in required_categories:
        assert category in source


def test_admin_api_key_ui_posts_profile_payload_to_settings_api_keys():
    source = _combined_admin_api_key_sources()

    assert "/settings/api-keys" in source
    assert "POST" in source or "post('/settings/api-keys'" in source
    assert "category" in source
    assert "role" in source
    assert "scopes" in source
    assert "quota_limit_override" in source
    assert "expires_at" in source
    assert "purpose" in source
    assert "issued_to" in source


def test_admin_api_key_ui_renders_one_time_raw_key_warning():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "one-time",
        "raw key",
        "will not be shown again",
        "Copy",
        "X-API-Key",
    ]

    for phrase in required_phrases:
        assert phrase in source


def test_admin_api_key_ui_renders_safe_metadata_table_without_raw_secret_fields():
    source = _combined_admin_api_key_sources()

    required_metadata = [
        "key_id",
        "prefix",
        "label",
        "category",
        "role",
        "scopes",
        "client_id",
        "user_id",
        "plan_id",
        "quota_limit",
        "quota_used",
        "status",
        "usage_count",
        "last_used_at",
        "created_at",
        "expires_at",
        "revoked_at",
    ]

    for field in required_metadata:
        assert field in source

    forbidden_rendering_markers = [
        "hashed",
        "api_key</td>",
        "api_key)",
        "api_key ||",
    ]

    for marker in forbidden_rendering_markers:
        assert marker not in source


def test_admin_api_key_ui_supports_refresh_and_revoke_actions():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "Refresh",
        "Revoke",
        "DELETE",
        "/settings/api-keys/",
        "confirm",
    ]

    for phrase in required_phrases:
        assert phrase in source


def test_admin_api_key_ui_declares_permission_behavior_for_admin_roles():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "owner_admin",
        "security_admin",
        "viewer_admin",
        "read-only",
        "create",
        "revoke",
    ]

    for phrase in required_phrases:
        assert phrase in source


def test_admin_api_key_ui_usage_examples_follow_current_host_not_localhost_rewrite():
    source = _combined_admin_api_key_sources()

    for phrase in (
        "curl",
        "X-API-Key",
        "/adapters/status",
        "/cgt/govern",
        "pmk_",
        "window.location.origin",
        "Usage examples for this host",
    ):
        assert phrase in source

    assert "127.0.0.1:8000" not in source
    assert "127.0.0.1:18080" not in source


def test_admin_api_key_ui_has_integration_key_preset():
    source = _combined_admin_api_key_sources()

    required_phrases = [
        "API Key for integration",
        "service_integration",
        "Server-to-server integration access",
        "Integration API key",
        "integration-client",
        "integration-user",
        "issuedTo",
        "categorySelect.value = 'service_integration'",
        "role: 'service'",
        "read:adapters",
        "read:governor",
        "run:govern",
    ]

    for phrase in required_phrases:
        assert phrase in source
