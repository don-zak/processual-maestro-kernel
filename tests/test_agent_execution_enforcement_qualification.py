from __future__ import annotations

import pytest

from processual_api.cgt_governor.execution_enforcement import (
    ExecutionEnforcementError,
    GovernedAgentExecutionRequest,
    GovernedExecutionGate,
)
from processual_api.cgt_governor.gateway.models import Agent, AgentState
from processual_api.cgt_governor.gateway.registry import AgentRegistry
from processual_api.cgt_governor.gateway.storage import MemoryStorage
from processual_api.cgt_governor.governance_core import GovernanceAction, GovernanceOutcome


class Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def execute(self, request: GovernedAgentExecutionRequest, *, restricted: bool) -> str:
        self.calls.append(("execute", restricted))
        return "exec:1"

    def repair(self, request: GovernedAgentExecutionRequest) -> str:
        self.calls.append(("repair", False))
        return "repair:1"

    def retry(self, request: GovernedAgentExecutionRequest) -> str:
        self.calls.append(("retry", False))
        return "retry:1"


class Planner:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, request: GovernedAgentExecutionRequest) -> str:
        self.calls += 1
        return "planner:1"


class Queue:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str, str]] = []

    def enqueue(self, *, agent_id: str, evaluation_id: str, reason_code: str, audit_ref: str) -> str:
        self.items.append((agent_id, evaluation_id, reason_code, audit_ref))
        return "queue:1"


def _agent(state: AgentState = AgentState.ACTIVE, *, profile: str = "default", priority: int = 3) -> Agent:
    return Agent(
        agent_id="agent-1",
        name="agent",
        role="worker",
        adapter_name="fixture",
        model="fixture",
        system_prompt="fixture",
        language="en",
        state=state,
        created_at="2026-08-23T00:00:00Z",
        last_state_change="2026-08-23T00:00:00Z",
        last_state_reason="fixture",
        priority=priority,
        risk_level="high",
        owner="owner",
        policy_profile=profile,
    )


def _outcome(action: GovernanceAction, state: AgentState = AgentState.ACTIVE) -> GovernanceOutcome:
    recommended = state
    if action is GovernanceAction.FREEZE:
        recommended = AgentState.FROZEN
    elif action is GovernanceAction.ESCALATE:
        recommended = AgentState.ESCALATED
    return GovernanceOutcome(
        agent_id="agent-1",
        evaluation_id="evaluation:1",
        action=action,
        reason_code="fixture_reason",
        risk_level="high",
        policy_profile="default",
        policy_version="agent-governance-policy/v1",
        calibration_version="calibration/default/v1",
        calibration_hash="hash",
        previous_state=state,
        recommended_state=recommended,
        confidence="high",
        audit_ref="audit:1",
    )


def _request() -> GovernedAgentExecutionRequest:
    return GovernedAgentExecutionRequest(
        agent_id="agent-1",
        evaluation_id="evaluation:1",
        task_ref="task:1",
        audit_ref="audit:1",
    )


def _gate(agent: Agent):
    registry = AgentRegistry(MemoryStorage())
    registry.register(agent)
    executor = Executor()
    planner = Planner()
    queue = Queue()
    return GovernedExecutionGate(
        registry=registry,
        executor=executor,
        planner_router=planner,
        supervisor_queue=queue,
    ), registry, executor, planner, queue


def test_keep_allows_active_execution() -> None:
    gate, registry, executor, _, _ = _gate(_agent())
    receipt = gate.enforce(_request(), _outcome(GovernanceAction.KEEP))
    assert receipt.executed is True
    assert receipt.disposition == "execution_allowed"
    assert receipt.agent_state is AgentState.ACTIVE
    assert executor.calls == [("execute", False)]
    assert registry.get("agent-1").state is AgentState.ACTIVE


@pytest.mark.parametrize(
    ("action", "expected_call", "expected_disposition"),
    [
        (GovernanceAction.REPAIR, "repair", "repair_cycle_started"),
        (GovernanceAction.RETRY, "retry", "retry_started"),
    ],
)
def test_repair_and_retry_have_real_executor_effects(action, expected_call, expected_disposition) -> None:
    gate, _, executor, _, _ = _gate(_agent())
    receipt = gate.enforce(_request(), _outcome(action))
    assert receipt.executed is True
    assert receipt.disposition == expected_disposition
    assert executor.calls == [(expected_call, False)]


def test_route_to_planner_uses_router_protocol() -> None:
    gate, _, executor, planner, _ = _gate(_agent())
    receipt = gate.enforce(_request(), _outcome(GovernanceAction.ROUTE_TO_PLANNER))
    assert receipt.execution_ref == "planner:1"
    assert planner.calls == 1
    assert executor.calls == []


def test_lower_priority_persists_authoritative_registry_change() -> None:
    gate, registry, executor, _, _ = _gate(_agent(priority=3))
    receipt = gate.enforce(_request(), _outcome(GovernanceAction.LOWER_PRIORITY))
    assert receipt.disposition == "priority_lowered"
    assert registry.get("agent-1").priority == 2
    assert executor.calls == []


def test_freeze_changes_state_and_blocks_subsequent_execution() -> None:
    gate, registry, executor, _, _ = _gate(_agent())
    first = gate.enforce(_request(), _outcome(GovernanceAction.FREEZE))
    assert first.agent_state is AgentState.FROZEN
    assert executor.calls == []

    frozen_outcome = _outcome(GovernanceAction.FREEZE, AgentState.FROZEN)
    second = gate.enforce(_request(), frozen_outcome)
    assert second.executed is False
    assert second.agent_state is AgentState.FROZEN
    assert executor.calls == []
    assert registry.get("agent-1").state is AgentState.FROZEN


def test_escalation_creates_supervisor_queue_without_silent_execution() -> None:
    gate, registry, executor, _, queue = _gate(_agent())
    receipt = gate.enforce(_request(), _outcome(GovernanceAction.ESCALATE))
    assert receipt.executed is False
    assert receipt.disposition == "supervisor_queue_created"
    assert registry.get("agent-1").state is AgentState.ESCALATED
    assert queue.items == [("agent-1", "evaluation:1", "fixture_reason", "audit:1")]
    assert executor.calls == []


def test_reject_never_calls_executor() -> None:
    gate, _, executor, _, _ = _gate(_agent())
    receipt = gate.enforce(_request(), _outcome(GovernanceAction.REJECT))
    assert receipt.executed is False
    assert receipt.disposition == "execution_rejected"
    assert executor.calls == []


def test_stale_governance_outcome_fails_closed() -> None:
    gate, registry, executor, _, _ = _gate(_agent())
    registry.change_state("agent-1", AgentState.FROZEN, "changed-after-decision")
    with pytest.raises(ExecutionEnforcementError, match="stale_governance_outcome"):
        gate.enforce(_request(), _outcome(GovernanceAction.KEEP))
    assert executor.calls == []


def test_request_and_outcome_binding_cannot_be_swapped() -> None:
    gate, _, executor, _, _ = _gate(_agent())
    bad = GovernedAgentExecutionRequest("agent-2", "evaluation:1", "task:1", "audit:1")
    with pytest.raises(ExecutionEnforcementError, match="governance_agent_mismatch"):
        gate.enforce(bad, _outcome(GovernanceAction.KEEP))
    assert executor.calls == []


def test_rehabilitation_is_restricted_until_proof_window_passes() -> None:
    gate, registry, executor, _, _ = _gate(_agent(AgentState.FROZEN))
    gate.start_rehabilitation("agent-1", reason="supervisor-approved")
    agent = registry.get("agent-1")
    assert agent.state is AgentState.REHABILITATING
    assert agent.policy_profile == "conservative"

    rehab_outcome = _outcome(GovernanceAction.KEEP, AgentState.REHABILITATING)
    receipt = gate.enforce(_request(), rehab_outcome)
    assert receipt.executed is True
    assert receipt.restricted is True
    assert executor.calls == [("execute", True)]

    assert gate.complete_rehabilitation(
        "agent-1",
        successful_proofs=2,
        required_proofs=3,
        target_profile="default",
        reason="proof-window",
    ) is False
    assert registry.get("agent-1").state is AgentState.REHABILITATING

    assert gate.complete_rehabilitation(
        "agent-1",
        successful_proofs=3,
        required_proofs=3,
        target_profile="default",
        reason="proof-window",
    ) is True
    assert registry.get("agent-1").state is AgentState.ACTIVE
    assert registry.get("agent-1").policy_profile == "default"


def test_rehabilitating_agent_without_conservative_profile_fails_closed() -> None:
    gate, _, executor, _, _ = _gate(_agent(AgentState.REHABILITATING, profile="default"))
    with pytest.raises(ExecutionEnforcementError, match="rehabilitation_requires_conservative_profile"):
        gate.enforce(_request(), _outcome(GovernanceAction.KEEP, AgentState.REHABILITATING))
    assert executor.calls == []
