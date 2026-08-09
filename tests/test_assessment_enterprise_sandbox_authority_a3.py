from dataclasses import fields

from processual_api.services.enterprise_qualification_18 import (
    QualificationDecision,
    QualificationGrant,
    TaskCredentialRecord,
    get_task_execution_policy,
)


def test_enterprise_sandbox_contracts_keep_production_and_runtime_connector_disabled() -> None:
    for contract_type in (
        QualificationDecision,
        QualificationGrant,
        TaskCredentialRecord,
    ):
        by_name = {field.name: field for field in fields(contract_type)}
        assert by_name["production_allowed"].default is False
        assert by_name["runtime_connector_approved"].default is False


def test_executable_enterprise_sandbox_policies_do_not_gain_production_authority() -> None:
    for track, task_id in (
        ("camara", "sandbox_capability_probe"),
        ("tmforum", "ctk_contract_probe"),
    ):
        policy = get_task_execution_policy(track, task_id)
        assert policy.executable is True
        assert policy.environment == "sandbox"
        assert policy.read_only is True
        assert policy.write_allowed is False
        assert policy.production_allowed is False
        assert policy.runtime_connector_approved is False
        assert policy.external_http_allowed is False
        assert policy.raw_secret_visible is False


def test_unknown_enterprise_task_remains_fail_closed() -> None:
    policy = get_task_execution_policy("operator", "unreviewed_assessment_probe")

    assert policy.executable is False
    assert policy.requires_qualification is True
    assert policy.production_allowed is False
    assert policy.runtime_connector_approved is False
    assert policy.external_http_allowed is False
    assert policy.raw_secret_visible is False
