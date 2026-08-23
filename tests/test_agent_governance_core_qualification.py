from __future__ import annotations

from dataclasses import fields

import pytest

from processual_api.cgt_governor.calibration_profiles import (
    CalibrationProfileError,
    load_calibration_profile,
)
from processual_api.cgt_governor.gateway.models import Agent, AgentState
from processual_api.cgt_governor.governance_core import (
    AgentGovernanceService,
    GovernanceAction,
    GovernanceOutcome,
)
from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationContractViolationError,
    PrivateEvaluationRequest,
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
)


POLICY_VERSION = "agent-governance-policy/v1"


def _agent(state: AgentState = AgentState.ACTIVE, profile: str = "default") -> Agent:
    return Agent(
        agent_id="agent-1",
        name="qualification-agent",
        role="worker",
        adapter_name="fixture",
        model="fixture",
        system_prompt="fixture",
        language="en",
        state=state,
        created_at="2026-08-23T00:00:00Z",
        last_state_change="2026-08-23T00:00:00Z",
        last_state_reason="fixture",
        risk_level="high",
        owner="owner-1",
        policy_profile=profile,
    )


def _request() -> PrivateEvaluationRequest:
    return PrivateEvaluationRequest(
        formation_ref="formation:1",
        evidence_ref="evidence:1",
        context_ref="context:1",
        evaluated_at="2026-08-23T00:00:00Z",
    )


class Provider:
    def __init__(self, next_gate: str = "keep", policy_version: str = POLICY_VERSION) -> None:
        self.next_gate = next_gate
        self.policy_version = policy_version
        self.calls = 0

    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        self.calls += 1
        return SanitizedPrivateDecision(
            existence_rank="stable",
            dominant_constraint="none",
            next_gate=self.next_gate,
            confidence_band="high",
            explanation_code="fixture_decision",
            policy_version=self.policy_version,
        )


class FailingProvider:
    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        raise RuntimeError("private detail must not cross boundary")


class MalformedProvider:
    def evaluate(self, request: PrivateEvaluationRequest):
        return {"next_gate": "keep"}


def _evaluate(service: AgentGovernanceService, agent: Agent) -> GovernanceOutcome:
    return service.evaluate(
        agent=agent,
        request=_request(),
        evaluation_id="evaluation:1",
        audit_ref="audit:1",
    )


def test_governance_outcome_has_canonical_required_fields() -> None:
    names = {field.name for field in fields(GovernanceOutcome)}
    assert {
        "agent_id",
        "evaluation_id",
        "action",
        "reason_code",
        "risk_level",
        "policy_profile",
        "policy_version",
        "calibration_version",
        "calibration_hash",
        "previous_state",
        "recommended_state",
        "confidence",
        "audit_ref",
    } == names


@pytest.mark.parametrize(
    ("state", "expected_action", "provider_calls"),
    [
        (AgentState.PENDING, GovernanceAction.REJECT, 0),
        (AgentState.ACTIVE, GovernanceAction.KEEP, 1),
        (AgentState.FROZEN, GovernanceAction.FREEZE, 0),
        (AgentState.ESCALATED, GovernanceAction.ESCALATE, 0),
        (AgentState.REHABILITATING, GovernanceAction.KEEP, 1),
        (AgentState.DEACTIVATED, GovernanceAction.REJECT, 0),
    ],
)
def test_all_six_agent_states_are_governed_without_bypass(
    state: AgentState,
    expected_action: GovernanceAction,
    provider_calls: int,
) -> None:
    provider = Provider()
    outcome = _evaluate(AgentGovernanceService(provider), _agent(state))
    assert outcome.action is expected_action
    assert provider.calls == provider_calls
    assert outcome.previous_state is state
    assert outcome.audit_ref == "audit:1"


@pytest.mark.parametrize(
    ("next_gate", "expected"),
    [
        ("keep", GovernanceAction.KEEP),
        ("repair", GovernanceAction.REPAIR),
        ("retry", GovernanceAction.RETRY),
        ("route_to_planner", GovernanceAction.ROUTE_TO_PLANNER),
        ("lower_priority", GovernanceAction.LOWER_PRIORITY),
        ("freeze", GovernanceAction.FREEZE),
        ("escalate", GovernanceAction.ESCALATE),
        ("reject", GovernanceAction.REJECT),
    ],
)
def test_all_canonical_governance_actions_are_representable(next_gate: str, expected: GovernanceAction) -> None:
    outcome = _evaluate(AgentGovernanceService(Provider(next_gate)), _agent())
    assert outcome.action is expected


def test_freeze_and_escalation_recommend_authoritative_lifecycle_state() -> None:
    frozen = _evaluate(AgentGovernanceService(Provider("freeze")), _agent())
    escalated = _evaluate(AgentGovernanceService(Provider("escalate")), _agent())
    assert frozen.recommended_state is AgentState.FROZEN
    assert escalated.recommended_state is AgentState.ESCALATED


def test_unknown_profile_fails_closed_without_silent_fallback() -> None:
    provider = Provider()
    with pytest.raises(CalibrationProfileError, match="unknown_calibration_profile"):
        _evaluate(AgentGovernanceService(provider), _agent(profile="does-not-exist"))
    assert provider.calls == 0


def test_calibration_profile_is_versioned_approved_and_observably_distinct() -> None:
    default = load_calibration_profile("default")
    conservative = load_calibration_profile("conservative")
    assert default.status == conservative.status == "approved"
    assert default.approved_by and conservative.approved_by
    assert default.profile_version != conservative.profile_version
    assert default.parameters_hash != conservative.parameters_hash

    default_outcome = _evaluate(AgentGovernanceService(Provider()), _agent(profile="default"))
    conservative_outcome = _evaluate(AgentGovernanceService(Provider()), _agent(profile="conservative"))
    assert default_outcome.calibration_hash != conservative_outcome.calibration_hash
    assert default_outcome.calibration_version != conservative_outcome.calibration_version


def test_policy_version_mismatch_fails_closed() -> None:
    with pytest.raises(PrivateEvaluationContractViolationError, match="private_evaluation_contract_violation"):
        _evaluate(AgentGovernanceService(Provider(policy_version="unexpected-policy/v9")), _agent())


def test_unknown_private_action_fails_closed() -> None:
    with pytest.raises(PrivateEvaluationContractViolationError, match="private_evaluation_contract_violation"):
        _evaluate(AgentGovernanceService(Provider(next_gate="unapproved_action")), _agent())


def test_provider_exception_is_sanitized_and_cannot_bypass_governance() -> None:
    with pytest.raises(PrivateEvaluationUnavailableError, match="private_evaluation_unavailable") as exc_info:
        _evaluate(AgentGovernanceService(FailingProvider()), _agent())
    assert "private detail" not in str(exc_info.value)


def test_malformed_private_decision_fails_closed() -> None:
    with pytest.raises(PrivateEvaluationContractViolationError, match="private_evaluation_contract_violation"):
        _evaluate(AgentGovernanceService(MalformedProvider()), _agent())
