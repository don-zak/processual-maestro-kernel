from processual_api.services.operator_pilot_handoff import (
    build_operator_pilot_handoff_package,
    render_operator_pilot_handoff_markdown,
)


def test_operator_pilot_handoff_14a_keeps_safe_guardrails() -> None:
    package = build_operator_pilot_handoff_package()
    guardrails = package["guardrails"]

    assert package["package_id"] == "operator-pilot-handoff-14a"
    assert package["handoff_status"] == "pending_operator_inputs"
    assert package["pilot_ready"] is False
    assert guardrails["sandbox_only"] is True
    assert guardrails["production_allowed"] is False
    assert guardrails["runtime_connector_approved"] is False
    assert guardrails["customer_credentials_present"] is False
    assert guardrails["external_http_allowed"] is False
    assert guardrails["production_writes_allowed"] is False
    assert guardrails["automatic_activation_allowed"] is False


def test_operator_pilot_handoff_14a_expands_supported_organization_types() -> None:
    package = build_operator_pilot_handoff_package()
    entity_types = {
        item["entity_type"] for item in package["entity_specializations"]
    }

    assert "telecom_operator" in entity_types
    assert "banking_fintech" in entity_types
    assert "government_public_services" in entity_types
    assert "university_research" in entity_types
    assert "healthcare_admin" in entity_types
    assert "insurance" in entity_types
    assert "utilities_energy" in entity_types
    assert "logistics_transport" in entity_types
    assert "enterprise_helpdesk" in entity_types
    assert "legal_compliance" in entity_types


def test_operator_pilot_handoff_14a_required_inputs_and_tools_are_present() -> None:
    package = build_operator_pilot_handoff_package()

    input_keys = {item["key"] for item in package["required_operator_inputs"]}
    tool_keys = {item["key"] for item in package["replay_tools"]}

    assert "api_documentation" in input_keys
    assert "sandbox_base_url" in input_keys
    assert "authentication_method" in input_keys
    assert "allowed_scopes_matrix" in input_keys
    assert "production_approval_path" in input_keys

    assert "rebuild_package" in tool_keys
    assert "copy_operator_checklist" in tool_keys
    assert "export_markdown" in tool_keys
    assert all(item["safe_operation"] for item in package["replay_tools"])


def test_operator_pilot_handoff_14a_markdown_export_is_safe() -> None:
    markdown = render_operator_pilot_handoff_markdown()

    assert "Operator Pilot Handoff" in markdown
    assert "Telecom operators" in markdown
    assert "Banks and fintech institutions" in markdown
    assert "No runtime connector is approved" in markdown
    assert "No external HTTP call is executed" in markdown

    forbidden_markers = [
        "raw_secret",
        "raw_secret_visible",
        "raw_key",
        "customer_password",
        "production_allowed: `True`",
        "runtime_connector_approved: `True`",
    ]

    for marker in forbidden_markers:
        assert marker not in markdown
