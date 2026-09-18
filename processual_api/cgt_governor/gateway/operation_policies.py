"""Server-owned public governance operation policies."""

from __future__ import annotations

from dataclasses import dataclass

from .governance_context import GovernanceRequestContext


@dataclass(frozen=True)
class OperationGovernancePolicy:
    operation_id: str
    required_scopes: tuple[str, ...] = ()
    require_factual_evidence: bool = False
    require_execution_evidence: bool = False
    require_task_sufficiency: bool = False
    require_runtime_attestation: bool = False
    fail_closed: bool = True

    def as_context(self) -> GovernanceRequestContext:
        return GovernanceRequestContext(
            required_scopes=self.required_scopes,
            require_factual_evidence=self.require_factual_evidence,
            require_execution_evidence=self.require_execution_evidence,
            require_task_sufficiency=self.require_task_sufficiency,
        )


_OPERATION_POLICIES: dict[str, OperationGovernancePolicy] = {
    "response.evaluate": OperationGovernancePolicy(operation_id="response.evaluate"),
    "workflow.create": OperationGovernancePolicy(
        operation_id="workflow.create",
        required_scopes=("workflow:create",),
        require_task_sufficiency=True,
    ),
    "workflow.checkpoint": OperationGovernancePolicy(
        operation_id="workflow.checkpoint",
        required_scopes=("workflow:checkpoint",),
        require_execution_evidence=True,
        require_runtime_attestation=True,
    ),
    "api_key.issue": OperationGovernancePolicy(
        operation_id="api_key.issue",
        required_scopes=("api_key:issue",),
        require_execution_evidence=True,
        require_runtime_attestation=True,
    ),
    "api_key.revoke": OperationGovernancePolicy(
        operation_id="api_key.revoke",
        required_scopes=("api_key:revoke",),
        require_execution_evidence=True,
        require_runtime_attestation=True,
    ),
    "sandbox.activate": OperationGovernancePolicy(
        operation_id="sandbox.activate",
        required_scopes=("sandbox:activate",),
        require_factual_evidence=True,
        require_execution_evidence=True,
        require_task_sufficiency=True,
        require_runtime_attestation=True,
    ),
    "integration.external_execute": OperationGovernancePolicy(
        operation_id="integration.external_execute",
        required_scopes=("integration:execute",),
        require_execution_evidence=True,
        require_task_sufficiency=True,
        require_runtime_attestation=True,
    ),
    "evaluation.runtime.task_execute": OperationGovernancePolicy(
        operation_id="evaluation.runtime.task_execute",
        required_scopes=("run:evaluation",),
        require_execution_evidence=True,
        require_runtime_attestation=True,
    ),
    "admin.agent_state_change": OperationGovernancePolicy(
        operation_id="admin.agent_state_change",
        required_scopes=("admin:agent_state",),
        require_execution_evidence=True,
        require_runtime_attestation=True,
    ),
}


def registered_operation_ids() -> tuple[str, ...]:
    return tuple(sorted(_OPERATION_POLICIES))


def get_operation_policy(operation_id: str) -> OperationGovernancePolicy | None:
    return _OPERATION_POLICIES.get(operation_id)


def merge_governance_contexts(
    base: GovernanceRequestContext,
    stricter: GovernanceRequestContext,
) -> GovernanceRequestContext:
    return GovernanceRequestContext(
        required_scopes=tuple(sorted(set(base.required_scopes) | set(stricter.required_scopes))),
        require_factual_evidence=base.require_factual_evidence or stricter.require_factual_evidence,
        require_execution_evidence=base.require_execution_evidence or stricter.require_execution_evidence,
        require_task_sufficiency=base.require_task_sufficiency or stricter.require_task_sufficiency,
    )
