from __future__ import annotations

from types import SimpleNamespace

from processual_kernel.adaptive.convergence import AdaptiveConvergenceMonitor
from processual_kernel.adaptive.metrics import AdaptiveMetricsCollector
from processual_kernel.adaptive_types import DecisionOutcome, PolicyPatch
from processual_kernel.types import AgentState, MaestroAction, WorkflowState


def _cycle(
    workflow_id: str = "wf",
    *,
    coverage: float = 1.0,
    checkpoint_confidence: float | None = 0.9,
    violations: tuple[str, ...] = (),
):
    checkpoint = None if checkpoint_confidence is None else SimpleNamespace(confidence=checkpoint_confidence)
    invariants = SimpleNamespace(violations=violations)
    return SimpleNamespace(
        workflow_id=workflow_id,
        outcome_coverage_ratio=coverage,
        checkpoint=checkpoint,
        runtime_invariants=invariants,
    )


def test_convergence_empty_and_window_clamping() -> None:
    monitor = AdaptiveConvergenceMonitor(window_size=1)
    assert monitor.window_size == 2

    report = monitor.evaluate("missing")
    assert report.stable is False
    assert report.window_size == 0
    assert report.avg_outcome_coverage == 0.0
    assert report.max_violation_count == 0
    assert report.avg_checkpoint_confidence == 0.0
    assert report.recommendation == "observe_more"
    assert report.reasons == ("no adaptive cycles have been recorded",)


def test_convergence_observe_reports_insufficient_window_and_low_signals() -> None:
    monitor = AdaptiveConvergenceMonitor(window_size=3, min_outcome_coverage=0.9, min_checkpoint_confidence=0.7)
    report = monitor.observe(
        _cycle(
            coverage=0.5,
            checkpoint_confidence=0.4,
            violations=("boundary", "approval"),
        )
    )

    assert report.stable is False
    assert report.window_size == 1
    assert report.avg_outcome_coverage == 0.5
    assert report.max_violation_count == 2
    assert report.avg_checkpoint_confidence == 0.4
    assert report.recommendation == "hold_or_demote"
    assert any("target window is 3" in reason for reason in report.reasons)
    assert any("average outcome coverage" in reason for reason in report.reasons)
    assert "runtime invariant violations observed: 2" in report.reasons
    assert any("checkpoint confidence" in reason for reason in report.reasons)


def test_convergence_stable_full_window_and_missing_checkpoint_default() -> None:
    monitor = AdaptiveConvergenceMonitor(window_size=2, min_outcome_coverage=0.8, min_checkpoint_confidence=0.6)
    first = monitor.observe(_cycle(coverage=0.8, checkpoint_confidence=None))
    assert first.avg_checkpoint_confidence == 1.0
    assert first.stable is False

    second = monitor.observe(_cycle(coverage=1.0, checkpoint_confidence=0.8))
    assert second.stable is True
    assert second.window_size == 2
    assert second.avg_outcome_coverage == 0.9
    assert second.avg_checkpoint_confidence == 0.8
    assert second.max_violation_count == 0
    assert second.recommendation == "eligible_for_cautious_expansion"
    assert second.reasons == ()


def test_convergence_window_is_bounded_and_workflows_are_independent() -> None:
    monitor = AdaptiveConvergenceMonitor(window_size=2)
    monitor.observe(_cycle("a", coverage=0.1))
    monitor.observe(_cycle("a", coverage=0.8))
    latest = monitor.observe(_cycle("a", coverage=1.0))

    assert latest.window_size == 2
    assert latest.avg_outcome_coverage == 0.9
    assert monitor.evaluate("b").recommendation == "observe_more"


def _workflow(state: WorkflowState, cost: float):
    return SimpleNamespace(state=state, last_coefficients=SimpleNamespace(M=cost))


def _handoff(state: AgentState, psi: float):
    return SimpleNamespace(state=state, psi=psi)


def _agent(state: AgentState):
    return SimpleNamespace(state=state)


def test_metrics_empty_kernel_defaults_and_low_quality_helper() -> None:
    collector = AdaptiveMetricsCollector()
    kernel = SimpleNamespace(workflows={}, handoffs={}, registry={})

    snapshot = collector.snapshot(kernel)
    assert snapshot.workflow_success_rate == 0.0
    assert snapshot.handoff_failure_rate == 0.0
    assert snapshot.recovery_time == 0.0
    assert snapshot.cost_per_successful_workflow == 0.0
    assert snapshot.false_retry_rate == 0.0
    assert snapshot.false_reroute_rate == 0.0
    assert snapshot.late_escalation_rate == 0.0
    assert snapshot.unnecessary_escalation_rate == 0.0
    assert snapshot.agent_bloat_ratio == 0.0
    assert snapshot.checkpoint_detection_accuracy == 1.0
    assert snapshot.policy_patch_success_rate == 1.0
    assert snapshot.outcome_coverage_ratio == 1.0
    assert snapshot.workflow_count == 0
    assert snapshot.decision_outcome_count == 0
    assert snapshot.checkpoint_count == 0
    assert collector._low_quality_rate([]) == 0.0


def test_metrics_aggregates_workflows_handoffs_agents_outcomes_and_checkpoints() -> None:
    collector = AdaptiveMetricsCollector()
    kernel = SimpleNamespace(
        workflows={
            "done": _workflow(WorkflowState.COMPLETED, 6.0),
            "open": _workflow(WorkflowState.ACTIVE, 2.0),
        },
        handoffs={
            "good": _handoff(AgentState.ACTIVE, 0.2),
            "inactive": _handoff(AgentState.ARCHIVED, 0.5),
            "negative": _handoff(AgentState.ACTIVE, -0.1),
        },
        registry={
            "a": _agent(AgentState.ACTIVE),
            "b": _agent(AgentState.ARCHIVED),
            "c": _agent(AgentState.QUARANTINED),
            "d": _agent(AgentState.ACTIVE),
        },
    )
    outcomes = [
        DecisionOutcome("r1", "retry", "x", "ok", decision_quality=0.2, recovery_time_delta=-4.0),
        DecisionOutcome("r2", MaestroAction.RETRY.value, "x", "ok", decision_quality=0.9, recovery_time_delta=-2.0),
        DecisionOutcome("rr1", "reroute", "x", "ok", decision_quality=0.1),
        DecisionOutcome("e1", "escalate", "x", "late", decision_quality=0.8),
        DecisionOutcome("e2", MaestroAction.ESCALATE.value, "x", "unnecessary", decision_quality=0.8),
        DecisionOutcome("e3", "escalate", "x", "failed", decision_quality=0.8),
    ]
    checkpoints = [SimpleNamespace(confidence=0.5), SimpleNamespace(confidence=0.9)]

    snapshot = collector.snapshot(kernel, outcomes=outcomes, checkpoints=checkpoints)
    assert snapshot.workflow_success_rate == 0.5
    assert snapshot.handoff_failure_rate == 0.6667
    assert snapshot.cost_per_successful_workflow == 8.0
    assert snapshot.false_retry_rate == 0.5
    assert snapshot.false_reroute_rate == 1.0
    assert snapshot.late_escalation_rate == 0.6667
    assert snapshot.unnecessary_escalation_rate == 0.3333
    assert snapshot.recovery_time == 3.0
    assert snapshot.agent_bloat_ratio == 0.5
    assert snapshot.checkpoint_detection_accuracy == 0.7
    assert snapshot.workflow_count == 2
    assert snapshot.decision_outcome_count == 6
    assert snapshot.checkpoint_count == 2


def test_metrics_handles_kernel_without_runtime_collections() -> None:
    snapshot = AdaptiveMetricsCollector().snapshot(SimpleNamespace())
    assert snapshot.workflow_count == 0
    assert snapshot.handoff_failure_rate == 0.0
    assert snapshot.agent_bloat_ratio == 0.0


def test_metrics_patch_success_and_ledger_coverage_paths() -> None:
    collector = AdaptiveMetricsCollector()
    kernel = SimpleNamespace(workflows={}, handoffs={}, registry={})
    patches = [
        PolicyPatch("min_edge_psi", 0.0, 0.1, "", "v1", "v2", 20),
        PolicyPatch("min_workflow_psi", 0.0, 0.1, "successful reason", "v2", "v3", 20),
    ]
    ledger = SimpleNamespace(coverage_ratio=lambda: 0.625)

    snapshot = collector.snapshot(
        kernel,
        ledger=ledger,
        applied_patches=patches,
        successful_patch_versions=("v2",),
    )
    assert snapshot.policy_patch_success_rate == 1.0
    assert snapshot.outcome_coverage_ratio == 0.625


def test_metrics_patch_failure_without_version_or_reason() -> None:
    kernel = SimpleNamespace(workflows={}, handoffs={}, registry={})
    patch = PolicyPatch("min_edge_psi", 0.0, 0.1, "", "v1", "v2", 20)

    snapshot = AdaptiveMetricsCollector().snapshot(kernel, applied_patches=(patch,))
    assert snapshot.policy_patch_success_rate == 0.0
