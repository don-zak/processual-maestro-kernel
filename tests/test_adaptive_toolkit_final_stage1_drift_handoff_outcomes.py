from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.types import MaestroAction


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.drift_detector = Mock()
    toolkit.handoff_advisor = Mock()
    toolkit.evaluator = Mock()
    toolkit.ledger = Mock()
    toolkit.strategy_bandit = Mock()
    toolkit.history_recorder = Mock()
    toolkit._record_history_event = Mock()
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    return toolkit


def test_scan_drift_observes_workflow_agents_and_active_handoffs() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(
        psi=0.82,
        steps={
            "s1": SimpleNamespace(assigned_agent_id="agent-b"),
            "s2": SimpleNamespace(assigned_agent_id="agent-a"),
            "s3": SimpleNamespace(assigned_agent_id=None),
        },
    )
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.kernel.registry.get.side_effect = lambda agent_id: {
        "agent-a": SimpleNamespace(psi=0.71, failure_streak=1),
        "agent-b": SimpleNamespace(psi=0.63, failure_streak=3),
    }[agent_id]
    toolkit.kernel.handoffs = {
        "edge-active": SimpleNamespace(source_agent_id="agent-a", target_agent_id="agent-x", psi=0.55),
        "edge-inactive": SimpleNamespace(source_agent_id="agent-x", target_agent_id="agent-y", psi=0.91),
    }
    policy = SimpleNamespace(drift_sensitivity=0.17)
    alert = SimpleNamespace(severity=SimpleNamespace(value="warning"))
    toolkit.drift_detector.observe.side_effect = [None, alert, None, None, None, None]

    result = toolkit.scan_drift("wf-1", policy=policy)

    assert toolkit.drift_detector.sensitivity == pytest.approx(0.17)
    assert toolkit.drift_detector.observe.call_args_list == [
        call("wf-1", "workflow", "psi", 0.82),
        call("agent-a", "agent", "psi", 0.71),
        call("agent-a", "agent", "failure_streak_inverse", 0.5),
        call("agent-b", "agent", "psi", 0.63),
        call("agent-b", "agent", "failure_streak_inverse", 0.25),
        call("edge-active", "handoff", "psi", 0.55),
    ]
    assert result == (alert,)
    drift_audit = toolkit._audit_adaptive.call_args
    assert drift_audit.args[1] == "agent-a"
    assert drift_audit.args[2]["workflow_id"] == "wf-1"
    assert drift_audit.args[2]["severity"] == "warning"


def test_advise_weak_handoffs_covers_threshold_trend_and_inactive_edges() -> None:
    toolkit = make_toolkit()
    toolkit.kernel.get_workflow.return_value = SimpleNamespace(
        steps={"s1": SimpleNamespace(assigned_agent_id="agent-a")}
    )
    toolkit.kernel.handoffs = {
        "edge-low": SimpleNamespace(
            source_agent_id="agent-a", target_agent_id="agent-b", psi=0.59, previous_psi=0.60
        ),
        "edge-trend": SimpleNamespace(
            source_agent_id="agent-z", target_agent_id="agent-a", psi=0.80, previous_psi=0.90
        ),
        "edge-healthy": SimpleNamespace(
            source_agent_id="agent-a", target_agent_id="agent-c", psi=0.85, previous_psi=0.86
        ),
        "edge-inactive": SimpleNamespace(
            source_agent_id="agent-x", target_agent_id="agent-y", psi=0.10, previous_psi=0.90
        ),
    }
    policy = SimpleNamespace(kernel_policy=SimpleNamespace(min_edge_psi=0.60))
    low = SimpleNamespace(recommend_mediator=True, confidence=0.8)
    trend = SimpleNamespace(recommend_mediator=False, confidence=0.7)
    toolkit.handoff_advisor.advise.side_effect = [low, trend]

    result = toolkit.advise_weak_handoffs("wf-1", policy=policy)

    assert result == (low, trend)
    assert toolkit.handoff_advisor.advise.call_args_list == [
        call(edge_id="edge-low", telemetry=None, edge_psi=0.59),
        call(edge_id="edge-trend", telemetry=None, edge_psi=0.80),
    ]
    assert toolkit._audit_adaptive.call_count == 2


def test_handoff_validation_and_repair_plan_delegate_and_persist() -> None:
    toolkit = make_toolkit()
    suggestion = SimpleNamespace(recommend_mediator=True, confidence=0.91)
    validation = SimpleNamespace(passed=True)
    toolkit.handoff_advisor.validate_payload.return_value = validation

    assert toolkit.validate_handoff_payload({"artifact": "ok"}, suggestion) is validation
    toolkit.handoff_advisor.validate_payload.assert_called_once_with({"artifact": "ok"}, suggestion)

    profile = SimpleNamespace(risk=SimpleNamespace(value="critical"))
    plan = toolkit.plan_handoff_repair("edge-7", suggestion=suggestion, profile=profile)

    assert plan.edge_id == "edge-7"
    assert plan.suggestion is suggestion
    assert plan.validation_required is True
    assert plan.mediator_agent_role == "Synthesizer"
    assert plan.human_review_required is True
    assert len(plan.steps) == 5
    toolkit._persist.assert_called_once_with("handoff_repair_plans", plan)
    repair_audit = toolkit._audit_adaptive.call_args
    assert repair_audit.args[1] == "edge-7"
    assert repair_audit.args[2]["human_review_required"] is True


def test_evaluate_outcome_records_history_and_tolerates_unknown_strategy_action() -> None:
    toolkit = make_toolkit()
    outcome = SimpleNamespace(decision_quality=0.84, actual_result="success")
    toolkit.evaluator.evaluate.return_value = outcome
    toolkit.ledger.attach_outcome.return_value = SimpleNamespace(workflow_id="wf-1")
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(name="policy")
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = policy
    history_event = SimpleNamespace(event_id="history-1")
    toolkit.history_recorder.record_outcome.return_value = history_event
    toolkit.strategy_bandit.record.side_effect = ValueError("unsupported action")

    result = toolkit.evaluate_outcome(
        "decision-1",
        actual_result="success",
        action="not-a-maestro-action",
        expected_effect="reduce-risk",
        quality_delta=0.2,
    )

    assert result is outcome
    toolkit.evaluator.evaluate.assert_called_once_with(
        decision_id="decision-1",
        action="not-a-maestro-action",
        expected_effect="reduce-risk",
        actual_result="success",
        quality_delta=0.2,
    )
    toolkit.history_recorder.record_outcome.assert_called_once_with("wf-1", outcome, policy=policy)
    toolkit._record_history_event.assert_called_once_with(history_event)
    toolkit._persist.assert_called_once_with("decision_outcomes", outcome)
    assert toolkit._audit_adaptive.call_args.args[2]["decision_quality"] == pytest.approx(0.84)


def test_budget_guard_skips_below_threshold_and_selects_risk_action() -> None:
    toolkit = make_toolkit()
    tempo = SimpleNamespace(budget_stop_threshold=0.80)

    assert toolkit.enforce_budget_guard(
        "wf-low", 0.79, SimpleNamespace(risk=SimpleNamespace(value="low")), tempo
    ) is None
    toolkit.kernel.intervene.assert_not_called()

    high_action = toolkit.enforce_budget_guard(
        "wf-high", 0.91, SimpleNamespace(risk=SimpleNamespace(value="high")), tempo
    )
    assert high_action is MaestroAction.ESCALATE
    toolkit.kernel.intervene.assert_called_once()
    args = toolkit.kernel.intervene.call_args.args
    assert args[:3] == ("wf-high", MaestroAction.ESCALATE, "wf-high")
    assert "0.91 exceeded threshold 0.80" in args[3]
    assert args[4] == {"cost_usage_ratio": 0.91, "budget_stop_threshold": 0.80}

    toolkit.kernel.intervene.reset_mock()
    normal_action = toolkit.enforce_budget_guard(
        "wf-normal", 0.80, SimpleNamespace(risk=SimpleNamespace(value="medium")), tempo
    )
    assert normal_action is MaestroAction.PAUSE
