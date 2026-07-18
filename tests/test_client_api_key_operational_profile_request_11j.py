from pathlib import Path

SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def test_integration_key_requests_carry_selected_operational_profile_metadata() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    markers = (
        "integrationOperationalProfileRequestLines",
        "selectedIntegrationOperationalProfile",
        "integration_key_profile_id=",
        "operational_profile_status=selected",
        "operational_profile_display_name=",
        "base_key_profile=",
        "operational_profile_environment=",
        "requested_scopes=",
        "forbidden_scopes=",
        "requires_enterprise_plan=",
        "requires_integration_readiness=",
        "requires_supervisor_for_write=",
        "production_allowed=",
        "runtime_connector_approved=",
        "operational_profile_next_action=",
    )
    for marker in markers:
        assert marker in js


def test_integration_key_request_message_includes_operational_profile_lines() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    assert "integrationKeyRequestMessage" in js
    assert ".concat(integrationOperationalProfileRequestLines()).join" in js
    assert "prepareIntegrationKeyRequest" in js
    assert "integration_key_provisioning" in js
    assert "integration_key_rotation" in js
    assert "integration_key_deactivation" in js


def test_integration_key_operational_profile_request_remains_safe() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    safe_markers = (
        "Production connector approval remains separate.",
        "Runtime connectors are not approved from this request.",
        "No raw integration secret is included.",
    )
    for marker in safe_markers:
        assert marker in js

    forbidden_markers = (
        "raw_secret",
        "customer_credentials",
        "production_connector_approved = true",
        "runtime_connector_approved = true",
        "connector_runtime_execute",
        "fetch(""http",
        "fetch('http",
    )
    for marker in forbidden_markers:
        assert marker not in js


def test_11j_does_not_add_backend_route_or_key_lifecycle() -> None:
    settings_py = Path("processual_api/routers/settings.py").read_text(encoding="utf-8")
    assert "/api-key-integration" in settings_py
    assert "/api-key-operational-profiles" not in settings_py
