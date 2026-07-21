from processual_api.integrations.api_key_operational_profiles import (
    get_api_key_operational_profile,
)
from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
)

PROFILE_ID = "enterprise_telecom_conformance_read"

EXPECTED_SCOPES = {
    "crm:read",
    "ticket:read",
    "helpdesk:read",
    "order:preview",
    "network:read",
    "network:diagnostics_read",
}


def test_enterprise_telecom_conformance_profile_is_default_deny() -> None:
    profile = get_api_key_operational_profile(
        PROFILE_ID
    )

    assert profile["environment"] == "sandbox"
    assert profile["read_only"] is True
    assert profile["write_allowed"] is False
    assert profile["restricted_allowed"] is False
    assert profile["production_allowed"] is False
    assert (
        profile["runtime_connector_approved"]
        is False
    )

    assert set(profile["allowed_scopes"]) == EXPECTED_SCOPES


def test_profile_scopes_exist_in_declared_connector_capabilities() -> None:
    connector_ids = (
        "telecom_crm_reference",
        "telecom_ticketing_reference",
        "telecom_order_management_reference",
        "telecom_network_assurance_reference",
    )

    connector_scopes = {
        capability.scope_id
        for connector_id in connector_ids
        for capability in (
            get_runtime_connector_contract(
                connector_id
            ).capabilities
        )
        if capability.access_mode == "read"
    }

    assert EXPECTED_SCOPES.issubset(
        connector_scopes
    )


def test_profile_contains_no_write_or_restricted_scope() -> None:
    profile = get_api_key_operational_profile(
        PROFILE_ID
    )

    unsafe_fragments = (
        "create",
        "update",
        "write",
        "execute",
        "delete",
        "adjust",
        "approve",
        "draft",
        "production",
        "runtime",
    )

    for scope_id in profile["allowed_scopes"]:
        assert not any(
            fragment in scope_id
            for fragment in unsafe_fragments
        )
