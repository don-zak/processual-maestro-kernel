from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.types import MaestroAction, WorkflowState


def make_toolkit(workflow_state: WorkflowState) -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.kernel.get_workflow.return_value = SimpleNamespace(
        state=workflow_state,
        steps={
            "a": SimpleNamespace(state=SimpleNamespace(value="completed")),
            "b": SimpleNamespace(state=SimpleNamespace(value="running")),
        },
    )
    toolkit.efficiency_governor = Mock()
    toolkit.pending_outcomes = Mock()
    toolkit.evaluate_outcome = Mock()
    toolkit.outcome_coverage_ratio = Mock(return_value=0.75)
    toolkit._outcome_sweep_plans = {}
    toolkit._auto_outcome_reports = {}
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    return toolkit


def pending_entry(decision_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        decision_id=decision_id,
        workflow_id="wf-1",
        action=MaestroAction.PAUSE,
        metadata={"expected_effect": "stabilize"},
    )


def test_auto_evaluate_pending_outcomes_infers_success_and_progress_delta() -> None:
    toolkit = make_toolkit(WorkflowState.COMPLETED)
    entry = pending_entry("dec-1")
    toolkit.pending_outcomes.return_value = (entry, pending_entry("other"))
    plan = SimpleNamespace(
        pending_count=1,
        batch_size=1,
        remaining_count=0,
        reason="one eligible",
        selected_decision_ids=("dec-1",),
    )
    toolkit.efficiency_governor.plan_outcome_sweep.return_value = plan
    outcome = SimpleNamespace(decision_id="dec-1")
    toolkit.evaluate_outcome.return_value = outcome

    report = toolkit.auto_evaluate_pending_outcomes(
        "wf-1", max_age_seconds=30.0, max_items=1, now=123.0
    )

    toolkit.efficiency_governor.plan_outcome_sweep.assert_called_once_with(
        "wf-1",
        1,
        max_batch_size=1,
        min_age_seconds=30.0,
        pending_entries=[entry],
        now=123.0,
    )
    toolkit.evaluate_outcome.assert_called_once_with(
        "dec-1",
        actual_result="success",
        action=MaestroAction.PAUSE,
        expected_effect="stabilize",
        quality_delta=0.10,
        cost_delta=0.0,
        latency_delta=0.0,
        success_probability_delta=0.05,
    )
    assert report.evaluated_count == 1
    assert report.skipped_count == 0
    assert report.outcome_coverage_ratio == 0.75
    assert report.outcomes == (outcome,)
    assert toolkit._outcome_sweep_plans["wf-1"] == [plan]
    assert toolkit._auto_outcome_reports["wf-1"] == [report]
    assert toolkit._persist.call_args_list == [
        call("outcome_sweep_plans", plan),
        call("auto_outcome_reports", report),
    ]


def test_auto_evaluate_pending_outcomes_uses_explicit_metrics() -> None:
    toolkit = make_toolkit(WorkflowState.RUNNING)
    entry = pending_entry("dec-2")
    toolkit.pending_outcomes.return_value = (entry,)
    toolkit.efficiency_governor.plan_outcome_sweep.return_value = SimpleNamespace(
        pending_count=1,
        batch_size=1,
        remaining_count=0,
        reason="selected",
        selected_decision_ids=("dec-2",),
    )
    toolkit.evaluate_outcome.return_value = SimpleNamespace(decision_id="dec-2")

    toolkit.auto_evaluate_pending_outcomes(
        "wf-1",
        actual_result="manual",
        quality_delta=0.2,
        cost_delta=-0.1,
        latency_delta=-0.3,
        success_probability_delta=0.4,
        now=10.0,
    )

    toolkit.evaluate_outcome.assert_called_once_with(
        "dec-2",
        actual_result="manual",
        action=MaestroAction.PAUSE,
        expected_effect="stabilize",
        quality_delta=0.2,
        cost_delta=-0.1,
        latency_delta=-0.3,
        success_probability_delta=0.4,
    )


def test_auto_evaluate_pending_outcomes_skips_unknown_selected_id_and_reports_remaining() -> None:
    toolkit = make_toolkit(WorkflowState.FAILED)
    entry = pending_entry("dec-3")
    toolkit.pending_outcomes.return_value = (entry,)
    plan = SimpleNamespace(
        pending_count=1,
        batch_size=1,
        remaining_count=2,
        reason="stale selection",
        selected_decision_ids=("missing",),
    )
    toolkit.efficiency_governor.plan_outcome_sweep.return_value = plan

    report = toolkit.auto_evaluate_pending_outcomes("wf-1", now=42.0)

    toolkit.evaluate_outcome.assert_not_called()
    assert report.evaluated_count == 0
    assert report.skipped_count == 2
    assert report.outcomes == ()
    assert report.reason == "auto outcome sweep from workflow state"
