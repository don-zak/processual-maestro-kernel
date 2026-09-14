from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from processual_api.cgt_governor.gateway.models import (
    Agent,
    AgentState,
    EvaluationRecord,
    GatewayAction,
)
from processual_api.cgt_governor.gateway.policies import PolicyEngine
from processual_api.cgt_governor.gateway.registry import AgentRegistry
from processual_api.cgt_governor.gateway.storage import MemoryStorage


def _agent(*, failures: int = 0, state: AgentState = AgentState.ACTIVE) -> Agent:
    now = datetime.now(UTC).isoformat()
    return Agent(
        agent_id="agent-test",
        name="Test Agent",
        role="worker",
        adapter_name="test",
        model="test-model",
        system_prompt="",
        language="en",
        state=state,
        created_at=now,
        last_state_change=now,
        last_state_reason="",
        consecutive_failures=failures,
    )


def _record(action: GatewayAction, reward: float = 0.0) -> EvaluationRecord:
    return EvaluationRecord(
        timestamp=datetime.now(UTC).isoformat(),
        client_query="q",
        agent_response="a",
        rank="transient",
        reward=reward,
        policy="deepen_or_clarify",
        policy_label="Transient",
        fate_vector={},
        repair_prompt="repair",
        action_taken=action,
    )


def _decide(agent: Agent, *, rank: str, hallucination: float = 0.0):
    return PolicyEngine.decide(
        agent=agent,
        fate_vector={
            "stability": 0.0,
            "hybridity": 0.0,
            "distortion": 0.0,
            "extinction": 1.0 if rank == "extinct" else 0.0,
            "collapse": 0.0,
            "flourishing": 0.0,
            "transient": 0.0,
        },
        rank=rank,
        reward=-0.5,
        policy="test-policy",
        repair_prompt="repair",
        risk_signals={"hallucination": hallucination},
    )


def _scores(*, hallucination: float = 0.0) -> dict[str, float]:
    return {
        "compatibility": 0.5,
        "coherence": 0.5,
        "structural_support": 0.5,
        "usefulness": 0.5,
        "complexity": 0.3,
        "fatigue": 0.1,
        "shock": 0.1,
        "lift": 0.5,
        "novelty": 0.3,
        "no_answer": 0.0,
        "hallucination": hallucination,
        "constraint_failure": 0.0,
        "speed": 0.5,
    }


def _governed_result(rank: str):
    return SimpleNamespace(
        fate=SimpleNamespace(
            stability=0.7 if rank == "stable" else 0.0,
            hybridity=0.0,
            distortion=0.0,
            extinction=1.0 if rank == "extinct" else 0.0,
            collapse=0.0,
            flourishing=0.0,
            transient=0.0,
        ),
        rank=SimpleNamespace(value=rank),
        reward=0.8 if rank == "stable" else -0.8,
        policy="accept" if rank == "stable" else "reject_regenerate",
        policy_label="Stable" if rank == "stable" else "Extinct",
        repair_prompt=None,
    )


def test_critical_hallucination_freezes_at_threshold() -> None:
    decision = _decide(_agent(), rank="extinct", hallucination=0.30)
    assert decision.action == GatewayAction.BLOCK
    assert decision.agent_state == AgentState.FROZEN


def test_hallucination_below_threshold_does_not_freeze() -> None:
    decision = _decide(_agent(), rank="extinct", hallucination=0.2999)
    assert decision.action == GatewayAction.BLOCK
    assert decision.agent_state == AgentState.ACTIVE


def test_raw_hallucination_is_not_read_from_fate_vector() -> None:
    decision = PolicyEngine.decide(
        agent=_agent(),
        fate_vector={"extinction": 1.0, "hallucination": 1.0},
        rank="extinct",
        reward=-0.5,
        policy="reject_regenerate",
        repair_prompt=None,
        risk_signals={"hallucination": 0.0},
    )
    assert decision.action == GatewayAction.BLOCK
    assert decision.agent_state == AgentState.ACTIVE


def test_third_repair_escalates_including_current_result() -> None:
    decision = _decide(_agent(failures=2), rank="hybrid")
    assert decision.action == GatewayAction.ESCALATE
    assert decision.agent_state == AgentState.ESCALATED


def test_third_block_escalates_including_current_result() -> None:
    decision = _decide(_agent(failures=2), rank="distorted")
    assert decision.action == GatewayAction.ESCALATE
    assert decision.agent_state == AgentState.ESCALATED


def test_current_pass_is_not_escalated_by_stale_failures() -> None:
    decision = _decide(_agent(failures=3), rank="stable")
    assert decision.action == GatewayAction.PASS
    assert decision.agent_state == AgentState.ACTIVE


def test_registry_counts_repair_and_block_and_pass_resets() -> None:
    registry = AgentRegistry(storage=MemoryStorage())
    agent = _agent()
    registry.register(agent)
    registry.add_evaluation(agent.agent_id, _record(GatewayAction.REPAIR))
    assert agent.consecutive_failures == 1
    registry.add_evaluation(agent.agent_id, _record(GatewayAction.BLOCK))
    assert agent.consecutive_failures == 2
    registry.add_evaluation(agent.agent_id, _record(GatewayAction.PASS, reward=1.0))
    assert agent.consecutive_failures == 0


def test_engine_propagates_hallucination_and_freezes(monkeypatch) -> None:
    from processual_api.cgt_governor import analyzer, governor
    from processual_api.cgt_governor.gateway import engine as engine_module

    agent = _agent()
    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(agent)
    monkeypatch.setattr(analyzer, "analyze_cgt", lambda *args, **kwargs: _scores(hallucination=0.4))
    monkeypatch.setattr(governor, "govern_answer", lambda *args, **kwargs: _governed_result("extinct"))
    monkeypatch.setattr(engine_module, "gateway_registry", registry)
    monkeypatch.setattr(engine_module, "sign_response", lambda payload: "sig")
    monkeypatch.setattr(engine_module.lifecycle_engine, "evaluate_agent", lambda current_agent: None)

    decision = engine_module.GatewayEngine.evaluate(agent.agent_id, "q", "a")
    assert decision is not None
    assert decision.agent_state == AgentState.FROZEN
    assert registry.get(agent.agent_id).state == AgentState.FROZEN


def test_engine_applies_rehabilitation(monkeypatch) -> None:
    from processual_api.cgt_governor import analyzer, governor
    from processual_api.cgt_governor.gateway import engine as engine_module

    agent = _agent()
    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(agent)
    monkeypatch.setattr(analyzer, "analyze_cgt", lambda *args, **kwargs: _scores())
    monkeypatch.setattr(governor, "govern_answer", lambda *args, **kwargs: _governed_result("stable"))
    monkeypatch.setattr(engine_module, "gateway_registry", registry)
    monkeypatch.setattr(engine_module, "sign_response", lambda payload: "sig")
    monkeypatch.setattr(engine_module.lifecycle_engine, "evaluate_agent", lambda current_agent: "rehabilitate")

    decision = engine_module.GatewayEngine.evaluate(agent.agent_id, "q", "a")
    assert decision is not None
    assert decision.agent_state == AgentState.REHABILITATING
    assert decision.lifecycle_recommendation == "rehabilitate"


def test_engine_surfaces_upgrade_without_state_mutation(monkeypatch) -> None:
    from processual_api.cgt_governor import analyzer, governor
    from processual_api.cgt_governor.gateway import engine as engine_module

    agent = _agent()
    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(agent)
    monkeypatch.setattr(analyzer, "analyze_cgt", lambda *args, **kwargs: _scores())
    monkeypatch.setattr(governor, "govern_answer", lambda *args, **kwargs: _governed_result("stable"))
    monkeypatch.setattr(engine_module, "gateway_registry", registry)
    monkeypatch.setattr(engine_module, "sign_response", lambda payload: "sig")
    monkeypatch.setattr(engine_module.lifecycle_engine, "evaluate_agent", lambda current_agent: "upgrade")

    decision = engine_module.GatewayEngine.evaluate(agent.agent_id, "q", "a")
    assert decision is not None
    assert decision.agent_state == AgentState.ACTIVE
    assert decision.lifecycle_recommendation == "upgrade"
    assert "upgrade" in decision.message.lower()
