from __future__ import annotations

import pickle

import processual_kernel
from processual_kernel import contracts
from processual_kernel import types as legacy_types


ENUM_CONTRACT_NAMES = (
    "AgentState",
    "AgentCriticality",
    "WorkflowState",
    "StepState",
    "MaestroAction",
)
TASK_CONTRACT_NAMES = ("TaskEnvelope", "TaskResult")
BOUNDARY_CONTRACT_NAMES = (
    "AgentSpec",
    "WorkflowStep",
    "WorkflowPlan",
    "MaestroEvent",
    "AgentRuntime",
    "AuditSink",
)


def test_enum_contracts_keep_legacy_and_public_object_identity() -> None:
    for name in ENUM_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert getattr(legacy_types, name) is contract
        assert getattr(processual_kernel, name) is contract


def test_enum_contracts_keep_legacy_serialization_identity() -> None:
    for name in ENUM_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert contract.__module__ == "processual_kernel.types"
        member = next(iter(contract))
        assert pickle.loads(pickle.dumps(member)) is member


def test_enum_contract_values_are_unchanged() -> None:
    assert legacy_types.AgentState.ACTIVE == "active"
    assert legacy_types.AgentCriticality.CRITICAL == "critical"
    assert legacy_types.WorkflowState.ESCALATED == "escalated"
    assert legacy_types.StepState.SKIPPED == "skipped"
    assert legacy_types.MaestroAction.FINALIZE == "finalize"


def test_task_contracts_keep_legacy_and_public_object_identity() -> None:
    for name in TASK_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert getattr(legacy_types, name) is contract
        assert getattr(processual_kernel, name) is contract


def test_task_contracts_keep_legacy_serialization_identity() -> None:
    envelope = contracts.TaskEnvelope(
        task_id="task-1",
        required_capability="analysis",
        payload={"value": 7},
    )
    result = contracts.TaskResult(
        task_id="task-1",
        agent_id="agent-1",
        ok=True,
        output={"accepted": True},
    )

    for contract, instance in (
        (contracts.TaskEnvelope, envelope),
        (contracts.TaskResult, result),
    ):
        assert contract.__module__ == "processual_kernel.types"
        assert pickle.loads(pickle.dumps(instance)) == instance


def test_task_contract_defaults_are_unchanged() -> None:
    envelope = legacy_types.TaskEnvelope(task_id="task-2", required_capability="routing")
    assert envelope.payload == {}
    assert envelope.priority == 0.5

    result = legacy_types.TaskResult(task_id="task-2", agent_id="agent-2", ok=False)
    assert result.output is None
    assert result.error is None
    assert result.latency_ms == 0.0
    assert result.cost == 0.0


def test_boundary_contracts_keep_legacy_object_identity() -> None:
    for name in BOUNDARY_CONTRACT_NAMES:
        contract = getattr(contracts, name)
        assert getattr(legacy_types, name) is contract

    for name in ("AgentSpec", "WorkflowStep", "WorkflowPlan", "MaestroEvent"):
        assert getattr(processual_kernel, name) is getattr(contracts, name)


def test_boundary_dataclasses_keep_legacy_serialization_identity() -> None:
    step = contracts.WorkflowStep(step_id="step-1", capability="analysis", instruction="inspect")
    values = (
        contracts.AgentSpec(agent_id="agent-1", role="reviewer"),
        step,
        contracts.WorkflowPlan(workflow_id="wf-1", goal="verify", steps=(step,)),
        contracts.MaestroEvent(
            workflow_id="wf-1",
            action=contracts.MaestroAction.OBSERVE,
            subject="wf-1",
            reason="created",
        ),
    )
    for value in values:
        assert type(value).__module__ == "processual_kernel.types"
        assert pickle.loads(pickle.dumps(value)) == value


def test_boundary_contract_defaults_are_unchanged() -> None:
    spec = legacy_types.AgentSpec(agent_id="agent-2", role="worker")
    assert spec.version == "0.2.0"
    assert spec.capabilities == ()
    assert spec.criticality is legacy_types.AgentCriticality.MEDIUM
    assert spec.metadata == {}

    step = legacy_types.WorkflowStep(step_id="step-2", capability="routing", instruction="route")
    assert step.depends_on == ()
    assert step.preferred_agent_id is None
    assert step.parallel_group is None
    assert step.max_retries == 1
    assert step.metadata == {}

    plan = legacy_types.WorkflowPlan(workflow_id="wf-2", goal="route", steps=(step,))
    assert plan.priority == 0.5
    assert plan.metadata == {}


def test_boundary_protocols_keep_legacy_module_identity() -> None:
    assert contracts.AgentRuntime.__module__ == "processual_kernel.types"
    assert contracts.AuditSink.__module__ == "processual_kernel.types"
