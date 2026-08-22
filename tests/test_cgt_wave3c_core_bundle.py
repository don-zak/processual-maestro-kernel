from __future__ import annotations

import pytest

from processual_api.cgt_governor.classifier import classify_rank, decide_policy, policy_info
from processual_api.cgt_governor.evaluator import (
    compute_fate_vector,
    constrained_possibility,
    existential_score,
    lift_score,
    maturity_score,
)
from processual_api.cgt_governor.gateway.engine import GatewayEngine
from processual_api.cgt_governor.gateway.lifecycle import LifecycleEngine
from processual_api.cgt_governor.gateway.models import (
    Agent,
    AgentState,
    EvaluationRecord,
    GatewayAction,
)
from processual_api.cgt_governor.gateway.policies import PolicyEngine
from processual_api.cgt_governor.types import ExistenceRank, FateVector
from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationUnavailableError,
)


def _fate(**overrides: float) -> FateVector:
    values = {
        "stability": 0.0,
        "hybridity": 0.0,
        "distortion": 0.0,
        "extinction": 0.0,
        "collapse": 0.0,
        "flourishing": 0.0,
        "transient": 0.0,
    }
    values.update(overrides)
    return FateVector(**values)


def _agent(
    *,
    state: AgentState = AgentState.ACTIVE,
    rewards: list[float] | None = None,
    failures: int = 0,
) -> Agent:
    rewards = list(rewards or [])
    history = [
        EvaluationRecord(
            timestamp=f"t{i}",
            client_query="q",
            agent_response="a",
            rank="stable",
            reward=value,
            policy="accept",
            policy_label="Stable - Accept",
            fate_vector={},
            repair_prompt=None,
            action_taken=GatewayAction.PASS,
        )
        for i, value in enumerate(rewards)
    ]
    return Agent(
        agent_id="agent-1",
        name="Agent One",
        role="worker",
        adapter_name="mock",
        model="mock-model",
        system_prompt="system",
        language="en",
        state=state,
        created_at="now",
        last_state_change="now",
        last_state_reason="created",
        evaluation_history=history,
        performance_window=rewards,
        consecutive_failures=failures,
    )


@pytest.mark.parametrize(
    ("fate", "expected"),
    [
        (_fate(extinction=0.75, flourishing=1.0, stability=1.0), ExistenceRank.EXTINCT),
        (_fate(flourishing=0.65, stability=1.0), ExistenceRank.FLOURISHING),
        (_fate(stability=0.60, distortion=1.0), ExistenceRank.STABLE),
        (_fate(distortion=0.55, hybridity=1.0), ExistenceRank.DISTORTED),
        (_fate(hybridity=0.45), ExistenceRank.HYBRID),
        (_fate(), ExistenceRank.TRANSIENT),
    ],
)
def test_classify_rank_priority_and_fallback(
    fate: FateVector,
    expected: ExistenceRank,
) -> None:
    assert classify_rank(fate) is expected


def test_policy_lookup_known_unknown_and_invalid_rank() -> None:
    assert decide_policy(ExistenceRank.STABLE) == "accept"

    known = policy_info("repair_scaffold")
    assert known["rank"] == "hybrid"
    assert known["label"] == "Hybrid - Repair & Scaffold"

    assert policy_info("custom") == {
        "action": "custom",
        "label": "custom",
        "description": "",
        "emoji": "",
    }

    with pytest.raises(ValueError, match="Unsupported rank"):
        decide_policy("not-a-rank")  # type: ignore[arg-type]


def test_evaluator_scalar_helpers_cover_boundaries() -> None:
    assert existential_score(0.0, 0.0, 0.0) == 0.0
    assert 0.0 < existential_score(2.0, 0.5, -1.0) < 1.0
    assert constrained_possibility(2.0, 0.5, -1.0) == 0.0
    assert constrained_possibility(0.8, 0.5, 0.25) == pytest.approx(0.1)

    mature = maturity_score(1.0, 1.0, 1.0, 1.0, 0.0, 0.0)
    immature = maturity_score(0.0, 0.0, 0.0, 0.0, 1.0, 1.0)
    assert 0.0 <= immature < mature <= 1.0

    assert lift_score(1.0, 1.0, 1.0, 1.0) == 1.0
    assert lift_score(1.0, 1.0, 1.0, 1.0, overload=1.0) == 0.0


def test_compute_fate_vector_clamps_inputs_and_returns_all_components() -> None:
    fate = compute_fate_vector(
        compatibility=2.0,
        coherence=0.8,
        structural_support=0.7,
        usefulness=0.9,
        complexity=0.4,
        fatigue=-1.0,
        shock=0.2,
        lift=0.6,
        novelty=1.2,
        no_answer=0.0,
        hallucination=0.1,
        constraint_failure=0.0,
    )

    assert isinstance(fate, FateVector)
    for value in (
        fate.stability,
        fate.hybridity,
        fate.distortion,
        fate.extinction,
        fate.collapse,
        fate.flourishing,
        fate.transient,
    ):
        assert 0.0 <= value <= 1.0


@pytest.mark.parametrize(
    (
        "rank",
        "hallucination",
        "failures",
        "expected_action",
        "expected_state",
        "repair_expected",
    ),
    [
        ("extinct", 0.3, 0, GatewayAction.BLOCK, AgentState.FROZEN, False),
        ("extinct", 0.1, 0, GatewayAction.BLOCK, AgentState.ACTIVE, False),
        ("distorted", 0.0, 0, GatewayAction.BLOCK, AgentState.ACTIVE, True),
        ("stable", 0.0, 3, GatewayAction.ESCALATE, AgentState.ESCALATED, True),
        ("hybrid", 0.0, 0, GatewayAction.REPAIR, AgentState.ACTIVE, True),
        ("transient", 0.0, 0, GatewayAction.REPAIR, AgentState.ACTIVE, True),
        ("stable", 0.0, 0, GatewayAction.PASS, AgentState.ACTIVE, False),
        ("flourishing", 0.0, 0, GatewayAction.PASS, AgentState.ACTIVE, False),
    ],
)
def test_policy_engine_rule_chain(
    rank: str,
    hallucination: float,
    failures: int,
    expected_action: GatewayAction,
    expected_state: AgentState,
    repair_expected: bool,
) -> None:
    decision = PolicyEngine.decide(
        agent=_agent(failures=failures),
        fate_vector={"hallucination": hallucination},
        rank=rank,
        reward=0.2,
        policy="policy",
        repair_prompt="repair this",
    )

    assert decision.action is expected_action
    assert decision.agent_state is expected_state
    assert (decision.repair_prompt is not None) is repair_expected
    if rank == "flourishing":
        assert decision.policy_label == "Flourishing - Accept & Expand"


def test_lifecycle_ignores_inactive_and_short_history() -> None:
    assert (
        LifecycleEngine.evaluate_agent(
            _agent(state=AgentState.FROZEN, rewards=[1.0, 1.0, 1.0])
        )
        is None
    )
    assert LifecycleEngine.evaluate_agent(_agent(rewards=[1.0, 1.0])) is None


def test_lifecycle_recommendations_cover_all_actions() -> None:
    assert LifecycleEngine.evaluate_agent(_agent(rewards=[-0.8, -0.7, -0.6])) == "freeze"
    assert (
        LifecycleEngine.evaluate_agent(_agent(rewards=[0.2, 0.2, 0.2], failures=5))
        == "freeze"
    )
    assert (
        LifecycleEngine.evaluate_agent(_agent(rewards=[0.2, 0.2, -0.2, -0.2, -0.2]))
        == "escalate"
    )
    assert (
        LifecycleEngine.evaluate_agent(_agent(rewards=[0.9, 1.0, 1.4, 1.5, 1.6]))
        == "upgrade"
    )
    assert LifecycleEngine.evaluate_agent(_agent(rewards=[-0.1, -0.1, -0.1])) == "rehabilitate"
    assert LifecycleEngine.evaluate_agent(_agent(rewards=[0.2, 0.2, 0.2])) is None


class _FakeRegistry:
    def __init__(self, agent: Agent | None) -> None:
        self.agent = agent

    def get(self, agent_id: str) -> Agent | None:
        del agent_id
        return self.agent


def test_gateway_engine_returns_none_for_unknown_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    import processual_api.cgt_governor.gateway.engine as engine_module

    monkeypatch.setattr(engine_module, "gateway_registry", _FakeRegistry(None))
    assert GatewayEngine.evaluate("missing", "q", "a") is None


def test_gateway_engine_blocks_unavailable_agent_without_private_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import processual_api.cgt_governor.gateway.engine as engine_module

    agent = _agent(state=AgentState.FROZEN)
    monkeypatch.setattr(engine_module, "gateway_registry", _FakeRegistry(agent))

    decision = GatewayEngine.evaluate(agent.agent_id, "q", "a")

    assert decision is not None
    assert decision.action is GatewayAction.BLOCK
    assert decision.agent_state is AgentState.FROZEN
    assert "Cannot process requests" in decision.message


@pytest.mark.parametrize("state", [AgentState.ACTIVE, AgentState.REHABILITATING])
def test_gateway_engine_active_agents_fail_closed_at_private_boundary(
    monkeypatch: pytest.MonkeyPatch,
    state: AgentState,
) -> None:
    import processual_api.cgt_governor.gateway.engine as engine_module

    agent = _agent(state=state)
    monkeypatch.setattr(engine_module, "gateway_registry", _FakeRegistry(agent))

    with pytest.raises(
        PrivateEvaluationUnavailableError,
        match="private_evaluation_unavailable",
    ):
        GatewayEngine.evaluate(agent.agent_id, "question", "answer", language="ar")
