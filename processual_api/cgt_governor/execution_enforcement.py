"""Mandatory execution enforcement for canonical governance outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .calibration_profiles import load_calibration_profile
from .gateway.models import AgentState
from .gateway.registry import AgentRegistry
from .governance_core import GovernanceAction, GovernanceOutcome


class ExecutionEnforcementError(RuntimeError):
    """Raised when a governed request cannot be safely enforced."""


@dataclass(frozen=True, slots=True)
class GovernedAgentExecutionRequest:
    agent_id: str
    evaluation_id: str
    task_ref: str
    audit_ref: str


@dataclass(frozen=True, slots=True)
class GovernedAgentExecutionReceipt:
    agent_id: str
    evaluation_id: str
    action: GovernanceAction
    disposition: str
    agent_state: AgentState
    executed: bool
    restricted: bool
    execution_ref: str | None
    audit_ref: str


class ActionExecutor(Protocol):
    def execute(self, request: GovernedAgentExecutionRequest, *, restricted: bool) -> str: ...

    def repair(self, request: GovernedAgentExecutionRequest) -> str: ...

    def retry(self, request: GovernedAgentExecutionRequest) -> str: ...


class PlannerRouter(Protocol):
    def route(self, request: GovernedAgentExecutionRequest) -> str: ...


class SupervisorQueue(Protocol):
    def enqueue(self, *, agent_id: str, evaluation_id: str, reason_code: str, audit_ref: str) -> str: ...


class GovernedExecutionGate:
    """Apply a canonical GovernanceOutcome before any sensitive agent execution."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        executor: ActionExecutor,
        planner_router: PlannerRouter,
        supervisor_queue: SupervisorQueue,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._planner_router = planner_router
        self._supervisor_queue = supervisor_queue

    def enforce(
        self,
        request: GovernedAgentExecutionRequest,
        outcome: GovernanceOutcome,
    ) -> GovernedAgentExecutionReceipt:
        self._validate_binding(request, outcome)
        agent = self._registry.get(request.agent_id)
        if agent is None:
            raise ExecutionEnforcementError("agent_not_registered")
        if agent.state is not outcome.previous_state:
            raise ExecutionEnforcementError("stale_governance_outcome")

        action = outcome.action
        if action in {
            GovernanceAction.KEEP,
            GovernanceAction.REPAIR,
            GovernanceAction.RETRY,
            GovernanceAction.ROUTE_TO_PLANNER,
            GovernanceAction.LOWER_PRIORITY,
        } and agent.state not in (AgentState.ACTIVE, AgentState.REHABILITATING):
            raise ExecutionEnforcementError("agent_state_blocks_execution")

        if agent.state is AgentState.REHABILITATING and agent.policy_profile != "conservative":
            raise ExecutionEnforcementError("rehabilitation_requires_conservative_profile")

        execution_ref: str | None = None
        executed = False
        restricted = agent.state is AgentState.REHABILITATING
        disposition = action.value

        if action is GovernanceAction.KEEP:
            execution_ref = self._executor.execute(request, restricted=restricted)
            executed = True
            disposition = "execution_allowed"
        elif action is GovernanceAction.REPAIR:
            execution_ref = self._executor.repair(request)
            executed = True
            disposition = "repair_cycle_started"
        elif action is GovernanceAction.RETRY:
            execution_ref = self._executor.retry(request)
            executed = True
            disposition = "retry_started"
        elif action is GovernanceAction.ROUTE_TO_PLANNER:
            execution_ref = self._planner_router.route(request)
            executed = True
            disposition = "routed_to_planner"
        elif action is GovernanceAction.LOWER_PRIORITY:
            self._registry.change_priority(
                agent.agent_id,
                max(0, agent.priority - 1),
                reason=outcome.reason_code,
            )
            disposition = "priority_lowered"
        elif action is GovernanceAction.FREEZE:
            self._registry.change_state(agent.agent_id, AgentState.FROZEN, outcome.reason_code)
            disposition = "agent_frozen"
        elif action is GovernanceAction.ESCALATE:
            self._registry.change_state(agent.agent_id, AgentState.ESCALATED, outcome.reason_code)
            execution_ref = self._supervisor_queue.enqueue(
                agent_id=agent.agent_id,
                evaluation_id=outcome.evaluation_id,
                reason_code=outcome.reason_code,
                audit_ref=outcome.audit_ref,
            )
            disposition = "supervisor_queue_created"
        elif action is GovernanceAction.REJECT:
            disposition = "execution_rejected"
        else:
            raise ExecutionEnforcementError("unsupported_governance_action")

        current = self._registry.get(agent.agent_id)
        if current is None:
            raise ExecutionEnforcementError("agent_disappeared_during_enforcement")
        return GovernedAgentExecutionReceipt(
            agent_id=agent.agent_id,
            evaluation_id=outcome.evaluation_id,
            action=action,
            disposition=disposition,
            agent_state=current.state,
            executed=executed,
            restricted=restricted,
            execution_ref=execution_ref,
            audit_ref=outcome.audit_ref,
        )

    def start_rehabilitation(self, agent_id: str, *, reason: str) -> None:
        agent = self._registry.get(agent_id)
        if agent is None:
            raise ExecutionEnforcementError("agent_not_registered")
        if agent.state not in (AgentState.FROZEN, AgentState.ESCALATED):
            raise ExecutionEnforcementError("invalid_rehabilitation_entry_state")
        load_calibration_profile("conservative")
        self._registry.change_policy_profile(agent_id, "conservative", reason)
        self._registry.change_state(agent_id, AgentState.REHABILITATING, reason)

    def complete_rehabilitation(
        self,
        agent_id: str,
        *,
        successful_proofs: int,
        required_proofs: int,
        target_profile: str,
        reason: str,
    ) -> bool:
        agent = self._registry.get(agent_id)
        if agent is None:
            raise ExecutionEnforcementError("agent_not_registered")
        if agent.state is not AgentState.REHABILITATING:
            raise ExecutionEnforcementError("agent_not_rehabilitating")
        if required_proofs <= 0 or successful_proofs < 0:
            raise ExecutionEnforcementError("invalid_rehabilitation_proof_window")
        if successful_proofs < required_proofs:
            return False
        load_calibration_profile(target_profile)
        self._registry.change_policy_profile(agent_id, target_profile, reason)
        self._registry.change_state(agent_id, AgentState.ACTIVE, reason)
        return True

    @staticmethod
    def _validate_binding(
        request: GovernedAgentExecutionRequest,
        outcome: GovernanceOutcome,
    ) -> None:
        if request.agent_id != outcome.agent_id:
            raise ExecutionEnforcementError("governance_agent_mismatch")
        if request.evaluation_id != outcome.evaluation_id:
            raise ExecutionEnforcementError("governance_evaluation_mismatch")
        if request.audit_ref != outcome.audit_ref:
            raise ExecutionEnforcementError("governance_audit_mismatch")
        if not request.task_ref.strip() or request.task_ref != request.task_ref.strip():
            raise ExecutionEnforcementError("invalid_task_ref")
