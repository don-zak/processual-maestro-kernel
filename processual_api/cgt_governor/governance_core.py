"""Canonical agent-governance decision service.

This module composes existing public agent state, authoritative calibration
metadata, and the sanitized private-evaluation boundary into one versioned
GovernanceOutcome.  It deliberately does not execute an agent action; execution
enforcement is a separate boundary layered on top of this canonical outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationContractViolationError,
    PrivateEvaluationProvider,
    PrivateEvaluationRequest,
    SanitizedPrivateDecision,
    evaluate_through_private_boundary,
)

from .calibration_profiles import CalibrationProfile, load_calibration_profile
from .gateway.models import Agent, AgentState


class GovernanceContractError(RuntimeError):
    """Raised when public governance inputs cannot produce a safe canonical outcome."""


class GovernanceAction(StrEnum):
    KEEP = "keep"
    REPAIR = "repair"
    RETRY = "retry"
    ROUTE_TO_PLANNER = "route_to_planner"
    LOWER_PRIORITY = "lower_priority"
    FREEZE = "freeze"
    ESCALATE = "escalate"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class GovernanceOutcome:
    agent_id: str
    evaluation_id: str
    action: GovernanceAction
    reason_code: str
    risk_level: str
    policy_profile: str
    policy_version: str
    calibration_version: str
    calibration_hash: str
    previous_state: AgentState
    recommended_state: AgentState
    confidence: str
    audit_ref: str


_ACTION_MAP: dict[str, GovernanceAction] = {
    "keep": GovernanceAction.KEEP,
    "pass": GovernanceAction.KEEP,
    "repair": GovernanceAction.REPAIR,
    "retry": GovernanceAction.RETRY,
    "route_to_planner": GovernanceAction.ROUTE_TO_PLANNER,
    "lower_priority": GovernanceAction.LOWER_PRIORITY,
    "freeze": GovernanceAction.FREEZE,
    "freeze_agent": GovernanceAction.FREEZE,
    "escalate": GovernanceAction.ESCALATE,
    "escalate_to_human": GovernanceAction.ESCALATE,
    "reject": GovernanceAction.REJECT,
    "block": GovernanceAction.REJECT,
}

_STATE_ACTION: dict[AgentState, GovernanceAction] = {
    AgentState.PENDING: GovernanceAction.REJECT,
    AgentState.FROZEN: GovernanceAction.FREEZE,
    AgentState.ESCALATED: GovernanceAction.ESCALATE,
    AgentState.DEACTIVATED: GovernanceAction.REJECT,
}


def _required_reference(name: str, value: str) -> str:
    candidate = value.strip() if isinstance(value, str) else ""
    if not candidate or candidate != value or len(candidate) > 160:
        raise GovernanceContractError(f"invalid_{name}")
    return candidate


def _recommended_state(previous_state: AgentState, action: GovernanceAction) -> AgentState:
    if action is GovernanceAction.FREEZE:
        return AgentState.FROZEN
    if action is GovernanceAction.ESCALATE:
        return AgentState.ESCALATED
    if action is GovernanceAction.REJECT and previous_state is AgentState.DEACTIVATED:
        return AgentState.DEACTIVATED
    return previous_state


class AgentGovernanceService:
    """Produce one canonical governance outcome without bypass or profile fallback."""

    def __init__(self, provider: PrivateEvaluationProvider) -> None:
        self._provider = provider

    def evaluate(
        self,
        *,
        agent: Agent,
        request: PrivateEvaluationRequest,
        evaluation_id: str,
        audit_ref: str,
    ) -> GovernanceOutcome:
        evaluation_id = _required_reference("evaluation_id", evaluation_id)
        audit_ref = _required_reference("audit_ref", audit_ref)
        profile = load_calibration_profile(agent.policy_profile)

        state_action = _STATE_ACTION.get(agent.state)
        if state_action is not None:
            return self._state_outcome(
                agent=agent,
                profile=profile,
                evaluation_id=evaluation_id,
                audit_ref=audit_ref,
                action=state_action,
            )

        if agent.state not in (AgentState.ACTIVE, AgentState.REHABILITATING):
            raise GovernanceContractError("unsupported_agent_state")

        decision = evaluate_through_private_boundary(self._provider, request)
        return self._decision_outcome(
            agent=agent,
            profile=profile,
            decision=decision,
            evaluation_id=evaluation_id,
            audit_ref=audit_ref,
        )

    @staticmethod
    def _state_outcome(
        *,
        agent: Agent,
        profile: CalibrationProfile,
        evaluation_id: str,
        audit_ref: str,
        action: GovernanceAction,
    ) -> GovernanceOutcome:
        return GovernanceOutcome(
            agent_id=agent.agent_id,
            evaluation_id=evaluation_id,
            action=action,
            reason_code=f"agent_state_{agent.state.value}",
            risk_level=agent.risk_level,
            policy_profile=profile.profile_id,
            policy_version=profile.policy_version,
            calibration_version=profile.profile_version,
            calibration_hash=profile.parameters_hash,
            previous_state=agent.state,
            recommended_state=_recommended_state(agent.state, action),
            confidence="administrative",
            audit_ref=audit_ref,
        )

    @staticmethod
    def _decision_outcome(
        *,
        agent: Agent,
        profile: CalibrationProfile,
        decision: SanitizedPrivateDecision,
        evaluation_id: str,
        audit_ref: str,
    ) -> GovernanceOutcome:
        if decision.policy_version != profile.policy_version:
            raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
        action = _ACTION_MAP.get(decision.next_gate)
        if action is None:
            raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
        return GovernanceOutcome(
            agent_id=agent.agent_id,
            evaluation_id=evaluation_id,
            action=action,
            reason_code=decision.explanation_code,
            risk_level=agent.risk_level,
            policy_profile=profile.profile_id,
            policy_version=decision.policy_version,
            calibration_version=profile.profile_version,
            calibration_hash=profile.parameters_hash,
            previous_state=agent.state,
            recommended_state=_recommended_state(agent.state, action),
            confidence=decision.confidence_band,
            audit_ref=audit_ref,
        )
