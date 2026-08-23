from __future__ import annotations

import pytest

from processual_api.cgt_governor.execution_enforcement import (
    GovernedAgentExecutionRequest,
    GovernedExecutionGate,
)
from processual_api.cgt_governor.external_agent_adapter import (
    ExternalAgentExecutionError,
    ExternalAgentTarget,
    GenericExternalAgentAdapter,
)
from processual_api.cgt_governor.gateway.models import Agent, AgentState
from processual_api.cgt_governor.gateway.registry import AgentRegistry
from processual_api.cgt_governor.gateway.storage import MemoryStorage
from processual_api.cgt_governor.governance_benchmark import (
    GovernanceBenchmarkSample,
    build_governance_benchmark,
)
from processual_api.cgt_governor.governance_core import (
    AgentGovernanceService,
    GovernanceAction,
)
from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationRequest,
    SanitizedPrivateDecision,
)


class DecisionProvider:
    def __init__(self, next_gate: str) -> None:
        self.next_gate = next_gate

    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        return SanitizedPrivateDecision(
            existence_rank="stable",
            dominant_constraint="none",
            next_gate=self.next_gate,
            confidence_band="high",
            explanation_code="cross_agent_fixture",
            policy_version="agent-governance-policy/v1",
        )


class RecordingTransport:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, *, endpoint: str, payload: dict[str, object]) -> str:
        self.calls.append((endpoint, payload))
        if self.fail:
            raise RuntimeError("external provider failure detail")
        return "external-execution:1"


class Planner:
    def route(self, request: GovernedAgentExecutionRequest) -> str:
        return "planner:1"


class Queue:
    def enqueue(self, *, agent_id: str, evaluation_id: str, reason_code: str, audit_ref: str) -> str:
        return "supervisor:1"


def _agent() -> Agent:
    return Agent(
        agent_id="external-agent-1",
        name="external-agent",
        role="worker",
        adapter_name="generic-external",
        model="external",
        system_prompt="external",
        language="en",
        state=AgentState.ACTIVE,
        created_at="2026-08-23T00:00:00Z",
        last_state_change="2026-08-23T00:00:00Z",
        last_state_reason="fixture",
        risk_level="medium",
        owner="owner-1",
        policy_profile="default",
    )


def _request() -> PrivateEvaluationRequest:
    return PrivateEvaluationRequest(
        formation_ref="formation:external-1",
        evidence_ref="evidence:external-1",
        context_ref="context:external-1",
        evaluated_at="2026-08-23T00:00:00Z",
    )


def _execution_request() -> GovernedAgentExecutionRequest:
    return GovernedAgentExecutionRequest(
        agent_id="external-agent-1",
        evaluation_id="evaluation:external-1",
        task_ref="task:external-1",
        audit_ref="audit:external-1",
    )


def test_external_agent_flows_through_same_governance_and_execution_gate() -> None:
    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(_agent())
    outcome = AgentGovernanceService(DecisionProvider("keep")).evaluate(
        agent=registry.get("external-agent-1"),
        request=_request(),
        evaluation_id="evaluation:external-1",
        audit_ref="audit:external-1",
    )
    transport = RecordingTransport()
    adapter = GenericExternalAgentAdapter(
        target=ExternalAgentTarget("external-agent-1", "https://external.example/agent"),
        transport=transport,
    )
    receipt = GovernedExecutionGate(
        registry=registry,
        executor=adapter,
        planner_router=Planner(),
        supervisor_queue=Queue(),
    ).enforce(_execution_request(), outcome)

    assert receipt.executed is True
    assert receipt.execution_ref == "external-execution:1"
    assert transport.calls[0][1]["audit_ref"] == "audit:external-1"
    assert transport.calls[0][1]["operation"] == "execute"
    assert transport.calls[0][1]["restricted"] is False


def test_external_transport_failure_fails_closed_without_silent_execution() -> None:
    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(_agent())
    outcome = AgentGovernanceService(DecisionProvider("keep")).evaluate(
        agent=registry.get("external-agent-1"),
        request=_request(),
        evaluation_id="evaluation:external-1",
        audit_ref="audit:external-1",
    )
    transport = RecordingTransport(fail=True)
    adapter = GenericExternalAgentAdapter(
        target=ExternalAgentTarget("external-agent-1", "https://external.example/agent"),
        transport=transport,
    )
    gate = GovernedExecutionGate(
        registry=registry,
        executor=adapter,
        planner_router=Planner(),
        supervisor_queue=Queue(),
    )

    with pytest.raises(ExternalAgentExecutionError, match="external_agent_transport_failed") as exc_info:
        gate.enforce(_execution_request(), outcome)
    assert "provider failure detail" not in str(exc_info.value)
    assert len(transport.calls) == 1


def test_external_target_requires_https_and_rejects_embedded_credentials() -> None:
    with pytest.raises(ExternalAgentExecutionError, match="invalid_external_agent_endpoint"):
        ExternalAgentTarget("external-agent-1", "http://external.example/agent").validate()
    with pytest.raises(ExternalAgentExecutionError, match="invalid_external_agent_endpoint"):
        ExternalAgentTarget("external-agent-1", "https://user:pass@external.example/agent").validate()


def test_quantitative_governance_benchmark_metrics_are_deterministic() -> None:
    samples = [
        GovernanceBenchmarkSample("danger-a", True, False, False, GovernanceAction.FREEZE, "audit:1", 1.0),
        GovernanceBenchmarkSample("danger-a", True, False, False, GovernanceAction.FREEZE, "audit:2", 2.0),
        GovernanceBenchmarkSample("danger-b", True, False, False, GovernanceAction.KEEP, "audit:3", 3.0),
        GovernanceBenchmarkSample("safe-a", False, False, False, GovernanceAction.KEEP, "audit:4", 4.0),
        GovernanceBenchmarkSample("safe-b", False, False, False, GovernanceAction.REPAIR, "audit:5", 5.0),
        GovernanceBenchmarkSample("recovery", False, True, True, GovernanceAction.KEEP, "audit:6", 6.0),
    ]
    report = build_governance_benchmark(samples)

    assert report.sample_count == 6
    assert report.dangerous_output_interception_rate == pytest.approx(2 / 3)
    assert report.false_intervention_rate == pytest.approx(1 / 3)
    assert report.recovery_success_rate == 1.0
    assert report.decision_consistency_rate == 1.0
    assert report.audit_completeness_rate == 1.0
    assert report.p50_latency_ms == 3.0
    assert report.p95_latency_ms == 6.0
    assert report.p99_latency_ms == 6.0


def test_benchmark_detects_missing_audit_and_inconsistent_repeated_decisions() -> None:
    samples = [
        GovernanceBenchmarkSample("same", True, False, False, GovernanceAction.FREEZE, "audit:1", 1.0),
        GovernanceBenchmarkSample("same", True, False, False, GovernanceAction.KEEP, "", 1.0),
    ]
    report = build_governance_benchmark(samples)
    assert report.decision_consistency_rate == 0.5
    assert report.audit_completeness_rate == 0.5


def test_benchmark_rejects_empty_or_negative_latency_inputs() -> None:
    with pytest.raises(ValueError, match="governance_benchmark_requires_samples"):
        build_governance_benchmark([])
    with pytest.raises(ValueError, match="governance_benchmark_invalid_latency"):
        build_governance_benchmark(
            [GovernanceBenchmarkSample("x", False, False, False, GovernanceAction.KEEP, "audit:x", -1.0)]
        )
