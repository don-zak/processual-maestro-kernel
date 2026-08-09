from __future__ import annotations

import pytest

from processual_api.integrations.credential_profiles import (
    COMMON_REQUIRED_CUSTOMER_INPUTS,
)
from processual_api.integrations.enterprise_sandbox_qualification import (
    build_customer_sandbox_qualification,
)
from processual_api.integrations.scope_catalog import list_integration_scopes


def _profile_id() -> str:
    return "enterprise_core_api_reference"


def _read_scope_id() -> str:
    return next(
        scope.scope_id
        for scope in list_integration_scopes()
        if scope.access_level == "read" and scope.allowed_in_read_only_pilot
    )


def _supervised_scope_id() -> str:
    return next(
        scope.scope_id
        for scope in list_integration_scopes()
        if scope.access_level in {"write", "restricted"}
        and scope.requires_supervisor_approval
    )


def test_sandbox_qualification_is_blocked_with_missing_customer_inputs() -> None:
    payload = build_customer_sandbox_qualification(
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_read_scope_id()],
        provided_input_ids=[],
    )

    assert payload["configured"] is True
    assert payload["scope_posture"]["source"] == "catalog"
    assert payload["scope_posture"]["read_only_pilot_eligible"] is True
    assert payload["missing_input_ids"]
    assert payload["readiness"]["sandbox_ready"] == 0
    assert payload["sandbox_ready"] is False
    assert payload["security_controls_approved"] == 0
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert all(
        check["status"] == "blocked_missing_customer_inputs"
        for check in payload["readiness_checks"]
    )


def test_complete_customer_inputs_stop_at_supervised_security_boundary() -> None:
    payload = build_customer_sandbox_qualification(
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_read_scope_id()],
        provided_input_ids=list(COMMON_REQUIRED_CUSTOMER_INPUTS),
    )

    assert payload["missing_input_ids"] == []
    assert payload["security_controls_approved"] == 0
    assert payload["sandbox_ready"] is False
    assert payload["readiness"]["sandbox_ready"] == 0
    assert payload["next_action"] == (
        "Submit required security controls for supervised review."
    )
    assert all(
        check["status"] == "blocked_missing_security_controls"
        for check in payload["readiness_checks"]
    )
    assert all(check["missing_security_controls"] for check in payload["readiness_checks"])
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False


def test_sandbox_qualification_rejects_unknown_scope() -> None:
    with pytest.raises(ValueError, match="unsupported integration scope"):
        build_customer_sandbox_qualification(
            credential_profile_id=_profile_id(),
            requested_scope_ids=["unknown:scope"],
            provided_input_ids=[],
        )


def test_sandbox_qualification_rejects_unknown_customer_input_identifier() -> None:
    with pytest.raises(ValueError, match="unsupported customer input identifiers"):
        build_customer_sandbox_qualification(
            credential_profile_id=_profile_id(),
            requested_scope_ids=[_read_scope_id()],
            provided_input_ids=["raw_api_secret"],
        )


def test_sandbox_qualification_normalizes_and_deduplicates_identifiers() -> None:
    scope_id = _read_scope_id()
    first_input = COMMON_REQUIRED_CUSTOMER_INPUTS[0]

    payload = build_customer_sandbox_qualification(
        credential_profile_id="  ENTERPRISE_CORE_API_REFERENCE  ",
        requested_scope_ids=[scope_id.upper(), scope_id, f"  {scope_id}  "],
        provided_input_ids=[first_input.upper(), first_input, f"  {first_input}  "],
    )

    assert payload["credential_profile_id"] == _profile_id()
    assert payload["requested_scope_ids"] == [scope_id]
    assert payload["provided_input_ids"] == [first_input]


def test_supervised_scope_is_not_read_only_pilot_eligible() -> None:
    payload = build_customer_sandbox_qualification(
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_read_scope_id(), _supervised_scope_id()],
        provided_input_ids=[],
    )

    posture = payload["scope_posture"]
    assert posture["total"] == 2
    assert posture["supervisor_approval_required"] >= 1
    assert posture["write"] + posture["restricted"] >= 1
    assert posture["read_only_pilot_eligible"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False


def test_qualification_payload_contains_identifiers_not_secret_values() -> None:
    payload = build_customer_sandbox_qualification(
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_read_scope_id()],
        provided_input_ids=[COMMON_REQUIRED_CUSTOMER_INPUTS[0]],
    )

    serialized = repr(payload).lower()
    assert "credential_value" not in serialized
    assert "api_key_value" not in serialized
    assert "access_token" not in serialized
    assert "client_secret" not in serialized
    assert "endpoint_url" not in serialized
    assert payload["security_controls_approved"] == 0
