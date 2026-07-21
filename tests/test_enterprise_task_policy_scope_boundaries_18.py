from processual_api.services.enterprise_qualification_18 import (
    executable_task_ids,
    get_task_execution_policy,
)

PROFILE_ID = "enterprise_telecom_conformance_read"


def test_camara_probe_has_explicit_safe_binding_policy() -> None:
    policy = get_task_execution_policy(
        "camara",
        "sandbox_capability_probe",
    )

    assert policy.executable is True
    assert (
        policy.credential_profile_id
        == "telecom_operations_api_reference"
    )
    assert policy.operational_profile_id == PROFILE_ID
    assert policy.connector_id == "telecom_crm_reference"
    assert policy.allowed_scope_ids == ("crm:read",)
    assert policy.read_only is True
    assert policy.write_allowed is False
    assert policy.restricted_allowed is False


def test_tmforum_probe_has_explicit_safe_binding_policy() -> None:
    policy = get_task_execution_policy(
        "tmforum",
        "ctk_contract_probe",
    )

    assert policy.executable is True
    assert (
        policy.credential_profile_id
        == "telecom_operations_api_reference"
    )
    assert policy.operational_profile_id == PROFILE_ID
    assert (
        policy.connector_id
        == "telecom_ticketing_reference"
    )
    assert policy.allowed_scope_ids == ("ticket:read",)


def test_callback_delivery_remains_non_executable() -> None:
    policy = get_task_execution_policy(
        "operator",
        "callback_delivery_probe",
    )

    assert policy.executable is False
    assert policy.operational_profile_id is None
    assert policy.connector_id is None
    assert policy.allowed_scope_ids == ()

    assert (
        "callback_delivery_probe"
        not in executable_task_ids("operator")
    )


def test_unknown_task_defaults_to_no_binding_authority() -> None:
    policy = get_task_execution_policy(
        "camara",
        "unknown_task",
    )

    assert policy.executable is False
    assert policy.credential_profile_id is None
    assert policy.operational_profile_id is None
    assert policy.connector_id is None
    assert policy.allowed_scope_ids == ()
