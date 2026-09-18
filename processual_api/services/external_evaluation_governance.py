"""Governance Genome v2 qualification for External Evaluation runtime execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from processual_api.cgt_governor.gateway.governance_genome import governance_genome
from processual_api.cgt_governor.gateway.operation_policies import get_operation_policy
from processual_api.cgt_governor.gateway.runtime_execution_attestation import (
    RuntimeExecutionAttestation,
    build_runtime_execution_attestation,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GOVERNANCE_OPERATION_ID,
    validate_evaluation_governance_contract,
)


class ExternalEvaluationGovernanceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalEvaluationGovernancePreflight:
    operation_id: str
    governance_version: str
    claim_ceiling: str
    grant_id: str
    api_key_id: str
    actor_ref: str
    task_id: str
    binding_id: str
    source_digest: str


def qualify_external_evaluation_preflight(
    *,
    current_user: dict[str, Any],
    grant: dict[str, Any],
    task_id: str,
    binding_id: str,
) -> ExternalEvaluationGovernancePreflight:
    try:
        contract = validate_evaluation_governance_contract(grant)
    except ValueError as exc:
        raise ExternalEvaluationGovernanceError(str(exc)) from exc

    policy = get_operation_policy(EVALUATION_GOVERNANCE_OPERATION_ID)
    if policy is None or not policy.fail_closed:
        raise ExternalEvaluationGovernanceError(
            "evaluation_governance_operation_policy_unavailable"
        )

    scopes = {
        str(scope).strip().lower()
        for scope in current_user.get("scopes") or []
        if str(scope).strip()
    }
    if not set(policy.required_scopes).issubset(scopes):
        raise ExternalEvaluationGovernanceError(
            "evaluation_governance_authorization_failure"
        )

    grant_id = str(current_user.get("evaluation_grant_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()
    actor_ref = api_key_id
    normalized_task = str(task_id or "").strip().lower()
    normalized_binding = str(binding_id or "").strip()

    if not all((grant_id, api_key_id, actor_ref, normalized_task, normalized_binding)):
        raise ExternalEvaluationGovernanceError(
            "evaluation_governance_identity_incomplete"
        )
    if str(grant.get("grant_id") or "") != grant_id:
        raise ExternalEvaluationGovernanceError(
            "evaluation_governance_grant_identity_mismatch"
        )

    source_payload = {
        "operation_id": policy.operation_id,
        "governance_version": governance_genome.version,
        "claim_ceiling": governance_genome.runtime_claim_ceiling.value,
        "policy_digest": contract["policy_digest"],
        "grant_id": grant_id,
        "api_key_id": api_key_id,
        "actor_ref": actor_ref,
        "task_id": normalized_task,
        "binding_id": normalized_binding,
    }
    source_digest = hashlib.sha256(
        json.dumps(
            source_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()

    return ExternalEvaluationGovernancePreflight(
        operation_id=policy.operation_id,
        governance_version=governance_genome.version,
        claim_ceiling=governance_genome.runtime_claim_ceiling.value,
        grant_id=grant_id,
        api_key_id=api_key_id,
        actor_ref=actor_ref,
        task_id=normalized_task,
        binding_id=normalized_binding,
        source_digest=source_digest,
    )


def attest_external_evaluation_execution(
    preflight: ExternalEvaluationGovernancePreflight,
    *,
    execution_id: str,
    completed_at: str,
    succeeded: bool,
) -> RuntimeExecutionAttestation:
    execution_ref = str(execution_id or "").strip()
    if not execution_ref:
        raise ExternalEvaluationGovernanceError(
            "evaluation_execution_reference_missing"
        )
    try:
        return build_runtime_execution_attestation(
            operation_id=preflight.operation_id,
            actor_ref=preflight.actor_ref,
            execution_reference_id=execution_ref,
            source_digest=preflight.source_digest,
            performed_at=completed_at,
            attested_at=datetime.now(UTC).isoformat(),
            succeeded=succeeded,
        )
    except ValueError as exc:
        raise ExternalEvaluationGovernanceError(
            f"evaluation_execution_attestation_invalid:{exc}"
        ) from exc


def validate_external_evaluation_replay_governance(
    preflight: ExternalEvaluationGovernancePreflight,
    response: dict[str, Any],
) -> None:
    expected = {
        "governance_qualified": True,
        "governance_version": preflight.governance_version,
        "governance_operation_id": preflight.operation_id,
        "governance_claim_ceiling": preflight.claim_ceiling,
        "governance_fail_closed": True,
        "governance_source_digest": preflight.source_digest,
    }
    for key, value in expected.items():
        if response.get(key) != value:
            raise ExternalEvaluationGovernanceError(
                f"evaluation_replay_governance_mismatch:{key}"
            )
    digest = str(response.get("runtime_attestation_digest") or "")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ExternalEvaluationGovernanceError(
            "evaluation_replay_runtime_attestation_missing"
        )


def external_evaluation_governance_evidence(
    preflight: ExternalEvaluationGovernancePreflight,
    attestation: RuntimeExecutionAttestation,
) -> dict[str, Any]:
    return {
        "governance_qualified": True,
        "governance_version": preflight.governance_version,
        "governance_operation_id": preflight.operation_id,
        "governance_claim_ceiling": preflight.claim_ceiling,
        "governance_fail_closed": True,
        "governance_source_digest": preflight.source_digest,
        "runtime_attestation_digest": attestation.attestation_digest,
    }


__all__ = [
    "ExternalEvaluationGovernanceError",
    "ExternalEvaluationGovernancePreflight",
    "attest_external_evaluation_execution",
    "external_evaluation_governance_evidence",
    "qualify_external_evaluation_preflight",
    "validate_external_evaluation_replay_governance",
]
