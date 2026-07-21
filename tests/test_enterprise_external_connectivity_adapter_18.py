from datetime import UTC, datetime, timedelta

import pytest

from processual_api.services.enterprise_external_connectivity_adapter_18 import (
    EnterpriseR10BindingError,
    build_enterprise_r10_binding_plan,
)
from processual_api.services.enterprise_qualification_18 import (
    QualificationGrant,
)


def _grant(
    *,
    integration_track: str = "camara",
    approved_task_ids: tuple[str, ...] = (
        "sandbox_capability_probe",
    ),
) -> QualificationGrant:
    now = datetime.now(UTC)

    return QualificationGrant(
        grant_id="qgrant_demo",
        case_id="icase_demo",
        client_id="client_demo",
        integration_track=integration_track,
        approved_task_ids=approved_task_ids,
        approved_profile_ids=(
            "telecom_operations_api_reference",
        ),
        issued_by_supervisor_id=(
            "supervisor_demo"
        ),
        supervisor_session_key_id=(
            "supsk_internal"
        ),
        issued_at=now.isoformat(),
        expires_at=(
            now + timedelta(days=7)
        ).isoformat(),
        status="approved",
    )


def _institution_case() -> dict:
    return {
        "case_id": "icase_demo",
        "client_id": "client_demo",
        "integration_track": "camara",
        "status": "ready_for_review",
        "phase": "supervisor_decision",
    }


def _external_case(
    *,
    client_id: str = "client_demo",
    state: str = "readiness_approved",
    environment: str = "sandbox",
    profile: str = "telecom_operations_api_reference",
    connector_id: str = "telecom_crm_reference",
) -> dict:
    return {
        "case_id": "eccase_demo",
        "client_id": client_id,
        "connector_id": connector_id,
        "credential_profile_id": profile,
        "target_environment": environment,
        "state": state,
    }


def test_valid_binding_plan_is_safe_and_task_scoped() -> None:
    result = build_enterprise_r10_binding_plan(
        institution_case=_institution_case(),
        institution_task_id=(
            "sandbox_capability_probe"
        ),
        grant=_grant(),
        external_connectivity_case=(
            _external_case()
        ),
        requested_scope_ids=(
            "crm:read",
        ),
        connector_scope_ids=(
            "crm:read",
        ),
    )

    assert result["binding_status"] == (
        "validated"
    )
    assert result["institution_case_id"] == (
        "icase_demo"
    )
    assert result["institution_task_id"] == (
        "sandbox_capability_probe"
    )
    assert result["qualification_grant_id"] == (
        "qgrant_demo"
    )
    assert (
        result["external_connectivity_case_id"]
        == "eccase_demo"
    )
    assert result["next_required_state"] == (
        "qualification_key"
    )
    assert result["requested_scope_ids"] == (
        ("crm:read",)
    )

    assert result["production_allowed"] is False
    assert (
        result["runtime_connector_approved"]
        is False
    )
    assert (
        result["external_http_allowed"]
        is False
    )
    assert result["write_allowed"] is False
    assert result["raw_secret_visible"] is False

    serialized = repr(result).lower()

    assert "raw_key" not in serialized
    assert "key_hash" not in serialized
    assert "supervisor_session_key_id" not in serialized


def test_reference_task_cannot_bind_to_r10_key() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="task_credential_not_eligible",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "consent_reference"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case()
            ),
            requested_scope_ids=(
                "consent:read",
            ),
            connector_scope_ids=(
                "consent:read",
            ),
        )


def test_external_case_client_mismatch_is_denied() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="external_case_client_mismatch",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case(
                    client_id="client_other"
                )
            ),
            requested_scope_ids=(
                "crm:read",
            ),
            connector_scope_ids=(
                "crm:read",
            ),
        )


def test_non_sandbox_external_case_is_denied() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match=(
            "external_case_environment_not_sandbox"
        ),
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case(
                    environment="production"
                )
            ),
            requested_scope_ids=(
                "crm:read",
            ),
            connector_scope_ids=(
                "crm:read",
            ),
        )


def test_external_case_must_be_at_r10_qualification_state() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match=(
            "external_case_not_ready_for_qualification"
        ),
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case(
                    state="draft"
                )
            ),
            requested_scope_ids=(
                "crm:read",
            ),
            connector_scope_ids=(
                "crm:read",
            ),
        )


def test_operational_profile_must_match_task_policy() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="credential_profile_mismatch",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case(
                    profile="other_profile"
                )
            ),
            requested_scope_ids=(
                "crm:read",
            ),
            connector_scope_ids=(
                "crm:read",
            ),
        )


def test_scope_must_exist_in_connector_contract() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match=(
            "requested_scope_not_allowed_by_task_policy"
        ),
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case()
            ),
            requested_scope_ids=(
                "unknown:read",
            ),
            connector_scope_ids=(
                "crm:read",
            ),
        )


@pytest.mark.parametrize(
    "unsafe_scope",
    (
        "capability:write",
        "admin:capability",
        "secret:read",
        "runtime:execute",
        "production:read",
    ),
)
def test_unsafe_stage18_scopes_are_denied(
    unsafe_scope: str,
) -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="requested_scope_not_stage18_safe",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id=(
                "sandbox_capability_probe"
            ),
            grant=_grant(),
            external_connectivity_case=(
                _external_case()
            ),
            requested_scope_ids=(
                unsafe_scope,
            ),
            connector_scope_ids=(
                unsafe_scope,
            ),
        )


@pytest.mark.parametrize(
    ("state", "next_state"),
    (
        (
            "readiness_approved",
            "qualification_key",
        ),
        (
            "qualification_key_issued",
            "qualification_redemption",
        ),
        (
            "qualification_redeemed",
            "sandbox_api_key",
        ),
    ),
)
def test_binding_plan_reports_next_r10_action(
    state: str,
    next_state: str,
) -> None:
    result = build_enterprise_r10_binding_plan(
        institution_case=_institution_case(),
        institution_task_id=(
            "sandbox_capability_probe"
        ),
        grant=_grant(),
        external_connectivity_case=(
            _external_case(state=state)
        ),
        requested_scope_ids=(
            "crm:read",
        ),
        connector_scope_ids=(
            "crm:read",
        ),
    )

    assert result["next_required_state"] == (
        next_state
    )


def test_binding_plan_uses_registered_operational_profile() -> None:
    plan = build_enterprise_r10_binding_plan(
        institution_case=_institution_case(),
        institution_task_id="sandbox_capability_probe",
        grant=_grant(),
        external_connectivity_case=_external_case(
            connector_id="telecom_crm_reference",
        ),
        requested_scope_ids=("crm:read",),
        connector_scope_ids=("crm:read",),
    )

    assert (
        plan["operational_profile_id"]
        == "enterprise_telecom_conformance_read"
    )
    assert plan["connector_id"] == "telecom_crm_reference"
    assert plan["requested_scope_ids"] == ("crm:read",)


def test_requested_scope_outside_task_policy_is_rejected() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="requested_scope_not_allowed_by_task_policy",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id="sandbox_capability_probe",
            grant=_grant(),
            external_connectivity_case=_external_case(
                connector_id="telecom_crm_reference",
            ),
            requested_scope_ids=("ticket:read",),
            connector_scope_ids=(
                "crm:read",
                "ticket:read",
            ),
        )


def test_connector_must_match_task_policy() -> None:
    with pytest.raises(
        EnterpriseR10BindingError,
        match="connector_policy_mismatch",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=_institution_case(),
            institution_task_id="sandbox_capability_probe",
            grant=_grant(),
            external_connectivity_case=_external_case(
                connector_id="telecom_ticketing_reference",
            ),
            requested_scope_ids=("ticket:read",),
            connector_scope_ids=("ticket:read",),
        )


def test_callback_delivery_cannot_build_binding_plan() -> None:
    operator_case = {
        **_institution_case(),
        "integration_track": "operator",
    }

    with pytest.raises(
        EnterpriseR10BindingError,
        match="task_credential_not_eligible",
    ):
        build_enterprise_r10_binding_plan(
            institution_case=operator_case,
            institution_task_id="callback_delivery_probe",
            grant=_grant(
                integration_track="operator",
                approved_task_ids=(
                    "callback_delivery_probe",
                ),
            ),
            external_connectivity_case=_external_case(
                connector_id=(
                    "telecom_network_assurance_reference"
                ),
            ),
            requested_scope_ids=("network:read",),
            connector_scope_ids=("network:read",),
        )
