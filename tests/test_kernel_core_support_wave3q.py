from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel import audit as audit_mod
from processual_kernel import cgt_bridge as bridge_mod
from processual_kernel.audit import AuditEvent, AuditEventType, JsonlAuditSink, normalize_audit_event
from processual_kernel.cgt_bridge import CGTBridge
from processual_kernel.continuity import ContinuityEngine, MetricCoefficientMapper, clamp
from processual_kernel.types import AgentTelemetry, Coefficients, HandoffTelemetry, WorkflowTelemetry


class ExampleEnum(StrEnum):
    VALUE = "value"


@dataclass
class ExampleDataclass:
    number: int


@dataclass
class GovernanceDecision:
    agent_id: str = "agent-1"
    policy_version: str = "p1"
    decision_id: str = "d1"
    created_at: float = 123.0


@dataclass
class EdgeDecision:
    edge_id: str = "a->b"


@dataclass
class WorkflowDecision:
    workflow_id: str = "wf-1"


@dataclass
class MaestroEvent:
    subject: str = "subject-1"


@dataclass
class Aftermath:
    balance: float = 0.4


@dataclass
class OptionalBlock:
    score: float = 0.7


def test_audit_json_default_and_payload_dict_variants() -> None:
    assert audit_mod._json_default(ExampleDataclass(3)) == {"number": 3}
    assert audit_mod._json_default(ExampleEnum.VALUE) == "value"
    assert audit_mod._json_default(object()).startswith("<object object at")

    original = {"x": 1}
    copied = audit_mod._payload_dict(original)
    assert copied == original
    assert copied is not original
    assert audit_mod._payload_dict(ExampleDataclass(4)) == {"number": 4}
    assert "repr" in audit_mod._payload_dict(object())


def test_normalize_audit_event_preserves_envelope_and_special_classes() -> None:
    envelope = AuditEvent(AuditEventType.METRICS_SNAPSHOT, "subject", {"x": 1})
    assert normalize_audit_event(envelope) is envelope

    governance = normalize_audit_event(GovernanceDecision())
    assert governance.event_type is AuditEventType.GOVERNANCE_DECISION
    assert governance.subject_id == "agent-1"
    assert governance.policy_version == "p1"
    assert governance.decision_id == "d1"
    assert governance.created_at == 123.0

    edge = normalize_audit_event(EdgeDecision())
    assert edge.event_type is AuditEventType.EDGE_DECISION
    assert edge.subject_id == "a->b"

    workflow = normalize_audit_event(WorkflowDecision())
    assert workflow.event_type is AuditEventType.WORKFLOW_DECISION
    assert workflow.subject_id == "wf-1"

    maestro = normalize_audit_event(MaestroEvent())
    assert maestro.event_type is AuditEventType.MAESTRO_EVENT
    assert maestro.subject_id == "subject-1"


def test_normalize_audit_event_dict_known_unknown_and_timestamp_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audit_mod.time, "time", lambda: 55.0)

    known = normalize_audit_event(
        {
            "event_type": "runtime_command",
            "subject_id": "runtime-1",
            "policy_version": "p2",
            "decision_id": "d2",
            "created_at": 12.5,
        }
    )
    assert known.event_type is AuditEventType.RUNTIME_COMMAND
    assert known.subject_id == "runtime-1"
    assert known.created_at == 12.5

    unknown = normalize_audit_event({"event_type": "not-real", "workflow_id": "wf-x", "created_at": 0})
    assert unknown.event_type is AuditEventType.UNKNOWN
    assert unknown.subject_id == "wf-x"
    assert unknown.created_at == 55.0

    fallback = normalize_audit_event({"decision_id": "d3"})
    assert fallback.subject_id == "d3"


def test_jsonl_audit_sink_creates_parent_and_appends(tmp_path) -> None:
    path = tmp_path / "nested" / "audit.jsonl"
    sink = JsonlAuditSink(path)
    sink.write({"event_type": "metrics_snapshot", "subject_id": "s1", "payload_value": ExampleEnum.VALUE})
    sink.write(AuditEvent(AuditEventType.RUNTIME_COMMAND, "s2", {"dc": ExampleDataclass(9)}))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event_type"] == "metrics_snapshot"
    assert first["subject_id"] == "s1"
    assert second["event_type"] == "runtime_command"
    assert second["payload"] == {"dc": {"number": 9}}


def test_clamp_handles_bounds_custom_range_and_nonfinite() -> None:
    assert clamp(-1.0) == 0.0
    assert clamp(2.0) == 1.0
    assert clamp(0.4) == 0.4
    assert clamp(3.0, 1.0, 5.0) == 3.0
    assert clamp(math.inf, 2.0, 5.0) == 2.0
    assert clamp(math.nan, -1.0, 1.0) == -1.0


def test_metric_mapper_agent_alias_and_clamping() -> None:
    mapper = MetricCoefficientMapper()
    telemetry = AgentTelemetry(
        success_rate=0.8,
        cooperation_success=0.9,
        useful_handoff_rate=0.7,
        demand_rate=0.6,
        business_priority=0.8,
        resource_cost=0.5,
        overlap_score=0.4,
        policy_risk=0.3,
        failure_count=2,
        age_seconds=43_200,
        latency_p95_ms=5_000,
        queue_depth=0.7,
        custom={"need_boost": 0.5},
    )
    coeff = mapper.from_agent_telemetry(telemetry)
    assert coeff == mapper.from_telemetry(telemetry)
    assert coeff.T == pytest.approx(0.45 * 0.9 + 0.35 * 0.7 + 0.20 * 0.8)
    assert coeff.N == pytest.approx(0.45 * 0.6 + 0.25 * 0.8 + 0.20 * 0.7 + 0.10 * 0.5)
    assert 0.0 <= coeff.C <= 1.0
    assert 0.0 <= coeff.M <= 1.0

    saturated = mapper.from_agent_telemetry(
        AgentTelemetry(
            cooperation_success=10,
            useful_handoff_rate=10,
            success_rate=10,
            demand_rate=10,
            business_priority=10,
            queue_depth=10,
            resource_cost=10,
            overlap_score=10,
            policy_risk=10,
            failure_count=100,
            age_seconds=999_999,
            latency_p95_ms=999_999,
        )
    )
    assert saturated == Coefficients(1.0, 1.0, 1.0, 1.0)


def test_metric_mapper_handoff_and_workflow() -> None:
    mapper = MetricCoefficientMapper()
    handoff = mapper.from_handoff_telemetry(
        HandoffTelemetry(
            artifact_quality=0.9,
            context_preservation=0.8,
            acceptance_rate=0.7,
            rework_rate=0.2,
            latency_ms=2_000,
            ambiguity=0.1,
            policy_risk=0.3,
            demand_rate=0.6,
            custom={"handoff_priority": 0.9},
        )
    )
    assert handoff.T == pytest.approx(0.35 * 0.9 + 0.30 * 0.8 + 0.25 * 0.7 + 0.10 * 0.9)
    assert handoff.N == pytest.approx(0.70 * 0.6 + 0.30 * 0.9)
    assert 0.0 <= handoff.C <= 1.0
    assert 0.0 <= handoff.M <= 1.0

    workflow = mapper.from_workflow_telemetry(
        WorkflowTelemetry(
            goal_alignment=0.8,
            progress_rate=0.6,
            completion_confidence=0.7,
            coordination_quality=0.9,
            blocking_rate=0.2,
            rework_rate=0.1,
            cost_pressure=0.4,
            latency_pressure=0.3,
            risk_pressure=0.5,
            demand_rate=0.7,
            custom={"business_priority": 0.9},
        )
    )
    assert workflow.T == pytest.approx(0.35 * 0.9 + 0.35 * 0.8 + 0.30 * 0.7)
    assert workflow.N == pytest.approx(0.55 * 0.7 + 0.25 * 0.9 + 0.20 * 0.6)
    assert workflow.C == pytest.approx(0.30 * 0.4 + 0.25 * 0.3 + 0.25 * 0.1 + 0.20 * 0.2)
    assert workflow.M == pytest.approx(0.35 * 0.5 + 0.25 * 0.2 + 0.25 * 0.1 + 0.15 * 0.2)


def test_continuity_engine_validation_delta_step_and_normalization() -> None:
    with pytest.raises(ValueError, match="dt must be positive"):
        ContinuityEngine(0)

    engine = ContinuityEngine(dt=2.0)
    coeff = Coefficients(T=0.8, N=0.5, C=0.1, M=0.2)
    expected = ((0.8 * 0.5) - 0.1) * math.exp(-0.2) * 2.0
    assert engine.delta(coeff) == pytest.approx(expected)
    psi, dpsi = engine.step(1.5, coeff)
    assert dpsi == pytest.approx(expected)
    assert psi == pytest.approx(1.5 + expected)
    assert ContinuityEngine.normalize_psi(0.0) == pytest.approx(0.5)
    assert ContinuityEngine.normalize_psi(math.inf) == 0.0
    assert ContinuityEngine.normalize_psi(-math.inf) == 0.0
    assert 0.0 < ContinuityEngine.normalize_psi(10.0, scale=0.0) <= 1.0


def test_bridge_phase_and_feature_vector_clamp_values() -> None:
    bridge = CGTBridge()
    coeff = Coefficients(T=1.2, N=0.8, C=0.3, M=0.4)
    phase = bridge.coefficients_to_phase("phase", coeff, psi=2.0)
    assert phase.phase_id == "phase"
    assert phase.mass == pytest.approx(0.8)
    assert phase.mean_retention == pytest.approx(clamp((1.2 * 0.8) * (1.0 - 0.5 * 0.4)))
    assert phase.harmony == pytest.approx(clamp(1.2 * 0.7))
    assert phase.fatigue == pytest.approx(0.35)
    assert 0.5 < phase.self_potential < 1.0

    vector = bridge.feature_vector(coeff, psi=-2.0, dpsi=-0.5)
    assert vector["synergy"] == 1.0
    assert vector["need"] == 0.8
    assert vector["cost_inverse"] == 0.7
    assert vector["mortality_inverse"] == 0.6
    assert vector["dpsi_positive"] == 0.0
    assert vector["transition_gate"] == pytest.approx(0.5 + 0.35 * 0.4 + 0.25 * 0.3)


def test_bridge_evaluate_transition_delegates_expected_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    evaluator = Mock(return_value=sentinel)
    monkeypatch.setattr(bridge_mod, "evaluate_structural_transition", evaluator)
    bridge = CGTBridge(params=Mock())
    previous = Coefficients(T=0.6, N=0.7, C=0.2, M=0.1)
    current = Coefficients(T=0.5, N=0.8, C=0.4, M=0.3)

    result = bridge.evaluate_transition("entity", previous, current, -0.2, 0.1, -0.4, fatigue_counter=-3)
    assert result is sentinel
    kwargs = evaluator.call_args.kwargs
    assert kwargs["source_phase"].phase_id == "entity@previous"
    assert kwargs["target_phase"].phase_id == "entity@current"
    assert kwargs["gate_openness"] == 0.5
    assert kwargs["carrying_capacity"] == 0.8
    assert kwargs["node_fatigue"] == pytest.approx(0.7)
    assert kwargs["local_safety"] == pytest.approx(0.6)
    assert kwargs["continuation_channel"] == pytest.approx(0.42)
    assert kwargs["tau"] == 0.0
    assert kwargs["tau_star"] == 3.0
    assert kwargs["trigger"] == pytest.approx(1.0)
    assert kwargs["params"] is bridge.params


def test_bridge_evaluate_alias_forwards_failure_streak(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = CGTBridge()
    forwarded = Mock(return_value="report")
    monkeypatch.setattr(bridge, "evaluate_transition", forwarded)
    previous = Coefficients(0.1, 0.2, 0.3, 0.4)
    current = Coefficients(0.5, 0.6, 0.7, 0.8)

    assert bridge.evaluate("agent", previous, current, 1.0, 2.0, 0.3, 4) == "report"
    forwarded.assert_called_once_with(
        entity_id="agent",
        previous_coeff=previous,
        current_coeff=current,
        previous_psi=1.0,
        current_psi=2.0,
        dpsi=0.3,
        fatigue_counter=4,
    )


def test_bridge_report_to_dict_minimal_and_optional_blocks() -> None:
    rank = SimpleNamespace(value="stable")
    report = SimpleNamespace(
        transmissibility=0.1,
        retention=0.2,
        self_potential=0.3,
        lock_state=SimpleNamespace(locked=True, transition_gate=0.4),
        delay_gate=0.5,
        compatibility=0.6,
        transition_channel=0.7,
        aftermath=Aftermath(0.8),
        existence=None,
        possibility=None,
        dynamic_lift=None,
        fate_vector=None,
        existence_rank=None,
    )
    minimal = CGTBridge.report_to_dict(report)
    assert minimal["locked"] is True
    assert minimal["aftermath"] == {"balance": 0.8}
    assert "existence" not in minimal

    report.existence = OptionalBlock(0.1)
    report.possibility = OptionalBlock(0.2)
    report.dynamic_lift = OptionalBlock(0.3)
    report.fate_vector = OptionalBlock(0.4)
    report.existence_rank = rank
    full = CGTBridge.report_to_dict(report)
    assert full["existence"] == {"score": 0.1}
    assert full["possibility"] == {"score": 0.2}
    assert full["dynamic_lift"] == {"score": 0.3}
    assert full["fate_vector"] == {"score": 0.4}
    assert full["existence_rank"] == "stable"
