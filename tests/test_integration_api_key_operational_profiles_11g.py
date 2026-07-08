from pathlib import Path

import pytest

from processual_api.integrations.api_key_operational_profiles import (
    api_key_operational_profiles_payload,
    get_api_key_operational_profile,
    list_api_key_operational_profiles,
)


def test_api_key_operational_profiles_are_client_visible_and_safe():
    profiles = list_api_key_operational_profiles()

    assert profiles
    assert {profile["profile_id"] for profile in profiles} >= {
        "external_partner_access",
        "service_integration_read_only",
        "service_integration_support_ticketing",
        "service_integration_billing_read",
        "telecom_operations_sandbox",
        "document_metadata_access",
        "enterprise_core_status_read",
    }

    for profile in profiles:
        assert profile["client_visible"] is True
        assert profile["requires_enterprise_plan"] is True
        assert profile["requires_integration_readiness"] is True
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False
        assert "production_write" in profile["forbidden_scopes"]
        assert profile["base_key_profile"] in {"external_partner", "service_integration"}
        assert profile["environment"] == "sandbox"


def test_telecom_operations_sandbox_profile_preserves_guardrails():
    profile = get_api_key_operational_profile("telecom_operations_sandbox")

    assert profile["base_key_profile"] == "service_integration"
    assert profile["write_allowed"] is True
    assert profile["requires_supervisor_for_write"] is True
    assert profile["production_allowed"] is False
    assert profile["runtime_connector_approved"] is False
    assert "crm_customer:read" in profile["allowed_scopes"]
    assert "order_status:read" in profile["allowed_scopes"]
    assert "network_assurance_event:create" in profile["allowed_scopes"]
    assert "crm_customer:update" in profile["forbidden_scopes"]
    assert "billing:update" in profile["forbidden_scopes"]
    assert "payment:execute" in profile["forbidden_scopes"]


def test_operational_profiles_payload_is_public_safe():
    payload = api_key_operational_profiles_payload()

    assert payload["ok"] is True
    assert payload["catalog"] == "api_key_operational_profiles"
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["profile_count"] == len(payload["profiles"])

    for profile in payload["profiles"]:
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False
        assert profile["requires_enterprise_plan"] is True
        assert profile["requires_integration_readiness"] is True
        assert "production_write" in profile["forbidden_scopes"]


def test_unknown_operational_profile_is_rejected():
    with pytest.raises(KeyError):
        get_api_key_operational_profile("unknown_runtime_connector")


def test_operational_profiles_do_not_add_runtime_or_key_lifecycle():
    source = Path(
        "processual_api/integrations/api_key_operational_profiles.py"
    ).read_text(encoding="utf-8")

    forbidden_markers = (
        "requests.post",
        "requests.get",
        "httpx.",
        "urllib.request",
        "socket.",
        "issue_api_key",
        "create_api_key",
        "rotate_api_key",
        "revoke_api_key",
        "production_connector_approved = True",
        "runtime_connector_approved = True",
    )

    for marker in forbidden_markers:
        assert marker not in source
