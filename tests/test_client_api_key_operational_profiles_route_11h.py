from pathlib import Path

from processual_api.routers.settings import (
    _client_api_key_operational_profiles_payload,
)


def test_operational_profiles_are_hidden_when_integration_is_locked():
    payload = _client_api_key_operational_profiles_payload(enabled=False)

    assert payload["operational_profiles_enabled"] is False
    assert payload["operational_profiles"] == []
    assert payload["operational_profile_count"] == 0
    assert payload["raw_secret_visible"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["integration_readiness_required"] is True
    assert payload["supervisor_approval_required"] is True


def test_operational_profiles_are_exposed_only_as_safe_metadata_when_enabled():
    payload = _client_api_key_operational_profiles_payload(enabled=True)

    assert payload["operational_profiles_enabled"] is True
    assert payload["operational_profiles"]
    assert payload["operational_profile_count"] == len(payload["operational_profiles"])
    assert payload["raw_secret_visible"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False

    profile_ids = {profile["profile_id"] for profile in payload["operational_profiles"]}
    assert "telecom_operations_sandbox" in profile_ids
    assert "service_integration_read_only" in profile_ids

    for profile in payload["operational_profiles"]:
        assert profile["client_visible"] is True
        assert profile["requires_enterprise_plan"] is True
        assert profile["requires_integration_readiness"] is True
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False


def test_api_key_integration_route_carries_operational_profiles_safely():
    source = Path("processual_api/routers/settings.py").read_text(encoding="utf-8")

    assert '@router.get("/api-key-integration", response_model=dict)' in source
    assert "current_user: dict = Depends(get_current_user)" in source
    assert "api_key_operational_profiles_payload" in source
    assert "**_client_api_key_operational_profiles_payload(enabled=False)" in source
    assert "**_client_api_key_operational_profiles_payload(enabled=True)" in source
    assert '"raw_secret_visible": False' in source
    assert '"production_allowed": False' in source
    assert '"runtime_connector_approved": False' in source
