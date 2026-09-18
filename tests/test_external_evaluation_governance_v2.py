from __future__ import annotations

from processual_api.cgt_governor.gateway.governance_genome import governance_genome
from processual_api.cgt_governor.gateway.operation_policies import get_operation_policy
from processual_api.cgt_governor.gateway.runtime_execution_attestation import (
    runtime_attestation_issues,
)
from processual_api.integrations.api_key_access_policy import get_api_key_access_policy
from processual_api.services.evaluation_grants import (
    EVALUATION_GOVERNANCE_OPERATION_ID,
    EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID,
    evaluation_governance_contract,
    validate_evaluation_governance_contract,
)
from processual_api.services.external_evaluation_governance import (
    ExternalEvaluationGovernanceError,
    attest_external_evaluation_execution,
    external_evaluation_governance_evidence,
    qualify_external_evaluation_preflight,
)


def _grant() -> dict:
    return {
        "grant_id": "eval-governance-v2",
        "governance_contract": evaluation_governance_contract(),
    }


def _identity() -> dict:
    return {
        "sub": "owner-user",
        "user_id": "owner-user",
        "client_id": "external-evaluator",
        "api_key_id": "evalkey-1",
        "evaluation_grant_id": "eval-governance-v2",
        "scopes": ["run:evaluation"],
    }


def test_external_evaluation_operations_are_server_owned_and_fail_closed() -> None:
    grant_policy = get_operation_policy(EVALUATION_GOVERNANCE_OPERATION_ID)
    runtime_policy = get_operation_policy(EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID)
    assert grant_policy is not None
    assert runtime_policy is not None
    assert grant_policy.fail_closed is True
    assert runtime_policy.required_scopes == ("run:evaluation",)
    assert runtime_policy.require_execution_evidence is True
    assert runtime_policy.require_runtime_attestation is True
    assert runtime_policy.fail_closed is True


def test_canonical_runtime_endpoint_is_bound_to_governance_operation() -> None:
    policy = get_api_key_access_policy("POST", "/evaluation/runtime/task-execute")
    assert policy is not None
    assert policy.governance_operation_id == EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID


def test_grant_contract_is_exactly_bound_to_current_genome() -> None:
    contract = evaluation_governance_contract()
    assert contract["version"] == governance_genome.version
    assert contract["claim_ceiling"] == governance_genome.runtime_claim_ceiling.value
    assert contract["fail_closed"] is True
    assert contract["operation_id"] == EVALUATION_GOVERNANCE_OPERATION_ID
    assert contract["runtime_operation_id"] == EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID
    assert len(contract["policy_digest"]) == 64
    assert validate_evaluation_governance_contract({"governance_contract": contract}) == contract


def test_legacy_grant_without_governance_contract_fails_closed() -> None:
    try:
        validate_evaluation_governance_contract({})
    except ValueError as exc:
        assert str(exc) == "evaluation_grant_governance_contract_required"
    else:
        raise AssertionError("legacy grant unexpectedly passed governance validation")


def test_preflight_requires_governance_scope() -> None:
    identity = _identity()
    identity["scopes"] = []
    try:
        qualify_external_evaluation_preflight(
            current_user=identity,
            grant=_grant(),
            task_id="crm.customer_context",
            binding_id="binding-a",
        )
    except ExternalEvaluationGovernanceError as exc:
        assert str(exc) == "evaluation_governance_authorization_failure"
    else:
        raise AssertionError("missing governance scope unexpectedly passed")


def test_execution_attestation_closes_external_evaluation_lineage() -> None:
    preflight = qualify_external_evaluation_preflight(
        current_user=_identity(),
        grant=_grant(),
        task_id="crm.customer_context",
        binding_id="binding-a",
    )
    attestation = attest_external_evaluation_execution(
        preflight,
        execution_id="exec-1",
        completed_at="2026-09-18T20:00:00+00:00",
        execution_evidence_digest="b" * 64,
        succeeded=True,
    )
    assert attestation.operation_id == EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID
    assert attestation.source_digest != preflight.context_digest
    assert len(preflight.context_digest) == 64
    assert runtime_attestation_issues(
        attestation,
        operation_id=EVALUATION_RUNTIME_GOVERNANCE_OPERATION_ID,
        evaluated_at="2026-09-18T21:00:00+00:00",
    ) == ()

    evidence = external_evaluation_governance_evidence(preflight, attestation)
    assert evidence["governance_qualified"] is True
    assert evidence["governance_version"] == governance_genome.version
    assert evidence["governance_claim_ceiling"] == "E4"
    assert evidence["runtime_attestation_digest"] == attestation.attestation_digest
