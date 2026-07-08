from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def test_client_api_key_operational_profile_selector_markup_exists() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    markers = (
        "set-api-key-operational-profile-selector",
        "Choose operational purpose",
        "set-api-key-operational-profile-count",
        "set-api-key-operational-profile-enabled",
        "set-api-key-operational-profile-summary",
        "set-api-key-operational-profile-allowed-scopes",
        "set-api-key-operational-profile-forbidden-scopes",
        "set-api-key-operational-profile-readiness",
        "set-api-key-operational-profile-safety",
        "Production connector approval remains separate",
        "Runtime connectors are not approved from this selector",
        "Raw integration secrets are never displayed",
    )
    for marker in markers:
        assert marker in html


def test_client_api_key_operational_profile_selector_uses_11h_payload() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    markers = (
        "normalizeIntegrationOperationalProfiles",
        "renderIntegrationOperationalProfileSelector",
        "renderSelectedIntegrationOperationalProfile",
        "initIntegrationOperationalProfileSelector",
        "operational_profiles",
        "operational_profile_count",
        "allowed_scopes",
        "forbidden_scopes",
        "requires_enterprise_plan",
        "requires_integration_readiness",
        "requires_supervisor_for_write",
        "production_allowed",
        "runtime_connector_approved",
        "Production connector approval remains separate",
    )
    for marker in markers:
        assert marker in js


def test_client_api_key_operational_profile_selector_remains_ui_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    forbidden_js_markers = (
        "/settings/api-keys",
        "/admin",
        "encrypted_key",
        "hashed_key",
        "production_connector_approved = true",
        "runtime_connector_approved = true",
    )
    for marker in forbidden_js_markers:
        assert marker not in js
    assert "set-api-key-request-provisioning" in html
    assert "set-api-key-operational-profile-selector" in html
    assert "integration_key_profile_id" not in html


def test_client_api_key_operational_profile_selector_preserves_existing_controls() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = SETTINGS_JS.read_text(encoding="utf-8")
    for marker in (
        "set-api-key-integration-card",
        "set-api-key-integration-plan",
        "set-api-key-integration-status",
        "set-api-key-integration-count",
        "set-api-key-integration-scopes",
        "set-api-key-integration-keys",
        "set-api-key-request-provisioning",
        "set-api-key-request-rotation",
        "set-api-key-request-deactivation",
    ):
        assert marker in html
    for marker in (
        "applyApiKeyIntegration",
        "loadApiKeyIntegration",
        "renderIntegrationKeys",
        "prepareIntegrationKeyRequest",
        "integrationKeyRequestMessage",
    ):
        assert marker in js
