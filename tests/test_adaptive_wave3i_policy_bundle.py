from __future__ import annotations

from types import SimpleNamespace

from processual_kernel.adaptive.policy_critic import PolicyCritic
from processual_kernel.adaptive.policy_profiles import build_policy_profiles, get_policy_profile
from processual_kernel.adaptive.policy_selector import PolicySelector
from processual_kernel.adaptive.quality_gates import AdaptiveQualityGate
from processual_kernel.adaptive_types import (
    AgentCountBand,
    AmbiguityLevel,
    MetricsSnapshot,
    PolicyName,
    RiskLevel,
    RuntimeMode,
    TaskDuration,
    TaskProfile,
    TaskSize,
)
from processual_kernel.types import KernelPolicy, StepState


def _profile(
    *,
    size: TaskSize = TaskSize.MEDIUM,
    duration: TaskDuration = TaskDuration.MEDIUM,
    risk: RiskLevel = RiskLevel.MEDIUM,
    ambiguity: AmbiguityLevel = AmbiguityLevel.MEDIUM,
    budget_sensitivity: RiskLevel = RiskLevel.MEDIUM,
    metadata: dict | None = None,
) -> TaskProfile:
    return TaskProfile(
        size=size,
        duration=duration,
        risk=risk,
        ambiguity=ambiguity,
        agent_count=AgentCountBand.FEW,
        budget_sensitivity=budget_sensitivity,
        metadata=metadata or {},
    )


def _metrics(**overrides) -> MetricsSnapshot:
    values = {
        "workflow_success_rate": 1.0,
        "handoff_failure_rate": 0.0,
        "recovery_time": 0.0,
        "cost_per_successful_workflow": 1.0,
        "false_retry_rate": 0.0,
        "false_reroute_rate": 0.0,
        "late_escalation_rate": 0.0,
        "unnecessary_escalation_rate": 0.0,
        "agent_bloat_ratio": 0.0,
        "checkpoint_detection_accuracy": 1.0,
        "policy_patch_success_rate": 1.0,
        "outcome_coverage_ratio": 1.0,
        "workflow_count": 1,
        "decision_outcome_count": 1,
        "checkpoint_count": 1,
    }
    values.update(overrides)
    return MetricsSnapshot(**values)


def test_policy_profiles_build_all_named_profiles_and_preserve_base() -> None:
    base = KernelPolicy(max_step_attempts=4, min_edge_psi=-0.2, min_workflow_psi=-0.3, quarantine_policy_risk=0.95)
    profiles = build_policy_profiles(base)

    assert set(profiles) == set(PolicyName)
    assert profiles[PolicyName.FAST].kernel_policy.max_step_attempts == 1
    assert profiles[PolicyName.FAST].runtime_mode == RuntimeMode.OBSERVE
    assert profiles[PolicyName.BALANCED].kernel_policy.max_step_attempts == 4
    assert profiles[PolicyName.BALANCED].max_retries == 4
    assert profiles[PolicyName.CONSERVATIVE].kernel_policy.quarantine_policy_risk == 0.78
    assert profiles[PolicyName.CONSERVATIVE].kernel_policy.min_edge_psi == 0.0
    assert profiles[PolicyName.CONSERVATIVE].kernel_policy.min_workflow_psi == 0.02
    assert profiles[PolicyName.CONSERVATIVE].human_gate_required is True
    assert profiles[PolicyName.LONG_RUNNING].checkpoint_interval_minutes == 60
    assert profiles[PolicyName.QUALITY_FIRST].kernel_policy.max_step_attempts == 3
    assert profiles[PolicyName.COST_SAVING].parallel_execution is False
    assert profiles[PolicyName.EXPLORATORY].runtime_mode == RuntimeMode.OBSERVE
    assert profiles[PolicyName.CRITICAL_SAFETY].runtime_mode == RuntimeMode.RESTRICTED_CRITICAL
    assert profiles[PolicyName.CRITICAL_SAFETY].kernel_policy.quarantine_policy_risk == 0.65
    assert profiles[PolicyName.CRITICAL_SAFETY].kernel_policy.min_edge_psi == 0.05
    assert profiles[PolicyName.CRITICAL_SAFETY].kernel_policy.min_workflow_psi == 0.05


def test_get_policy_profile_accepts_enum_and_string_and_default_base() -> None:
    by_enum = get_policy_profile(PolicyName.BALANCED)
    by_string = get_policy_profile(PolicyName.BALANCED.value)

    assert by_enum.name == PolicyName.BALANCED
    assert by_string.name == PolicyName.BALANCED
    assert by_enum.policy_version == "balanced-1.0.0"
    assert by_string.kernel_policy.policy_version == "balanced-1.0.0"


def test_policy_selector_covers_priority_order_and_fallback() -> None:
    selector = PolicySelector(KernelPolicy(max_step_attempts=5))

    assert selector.select(_profile(risk=RiskLevel.CRITICAL)).name == PolicyName.CRITICAL_SAFETY
    assert selector.select(_profile(risk=RiskLevel.HIGH)).name == PolicyName.CONSERVATIVE
    assert selector.select(_profile(metadata={"quality_first": True})).name == PolicyName.QUALITY_FIRST
    assert selector.select(_profile(budget_sensitivity=RiskLevel.HIGH)).name == PolicyName.COST_SAVING
    assert selector.select(_profile(metadata={"cost_saving": True})).name == PolicyName.COST_SAVING
    assert selector.select(_profile(duration=TaskDuration.LONG)).name == PolicyName.LONG_RUNNING
    assert selector.select(_profile(ambiguity=AmbiguityLevel.HIGH)).name == PolicyName.EXPLORATORY
    assert selector.select(_profile(metadata={"exploratory": True})).name == PolicyName.EXPLORATORY
    assert selector.select(
        _profile(size=TaskSize.SMALL, duration=TaskDuration.SHORT, risk=RiskLevel.LOW)
    ).name == PolicyName.FAST
    assert selector.select(_profile()).name == PolicyName.BALANCED


def test_policy_selector_risk_precedes_metadata_shortcuts() -> None:
    selector = PolicySelector()
    critical = _profile(risk=RiskLevel.CRITICAL, metadata={"quality_first": True, "cost_saving": True})
    high = _profile(risk=RiskLevel.HIGH, metadata={"quality_first": True})

    assert selector.select(critical).name == PolicyName.CRITICAL_SAFETY
    assert selector.select(high).name == PolicyName.CONSERVATIVE


def _kernel_with_steps(*steps):
    workflow = SimpleNamespace(steps={f"s{i}": step for i, step in enumerate(steps)})
    return SimpleNamespace(get_workflow=lambda workflow_id: workflow)


def _step(state: StepState, attempts: int, max_retries: int):
    return SimpleNamespace(state=state, attempts=attempts, step=SimpleNamespace(max_retries=max_retries))


def test_policy_critic_stable_workflow_returns_no_patch() -> None:
    policy = get_policy_profile(PolicyName.BALANCED)
    kernel = _kernel_with_steps(_step(StepState.COMPLETED, 1, 2))

    critique = PolicyCritic().review(kernel, "wf-stable", policy)

    assert critique.workflow_id == "wf-stable"
    assert critique.policy_name == PolicyName.BALANCED
    assert critique.findings == ("policy behavior was stable; no patch recommended",)
    assert critique.suggested_changes == ()
    assert critique.confidence == 0.55


def test_policy_critic_detects_failures_weak_handoff_and_low_quality_outcome() -> None:
    policy = get_policy_profile(PolicyName.BALANCED)
    kernel = _kernel_with_steps(
        _step(StepState.FAILED, 2, 2),
        _step(StepState.FAILED, 3, 5),
    )
    checkpoints = [SimpleNamespace(risks=("weak_handoffs:edge-a",))]
    outcomes = [SimpleNamespace(decision_quality=0.2)]

    critique = PolicyCritic().review(kernel, "wf-risky", policy, checkpoints=checkpoints, outcomes=outcomes)

    assert "failed steps exhausted retries; reroute or mediator should be considered" in critique.findings
    assert "retry was repeated without recovery on at least one step" in critique.findings
    assert "handoff degraded during checkpoint review" in critique.findings
    assert "one or more governance decisions scored below quality threshold" in critique.findings
    assert {patch.field for patch in critique.suggested_changes} == {"max_step_attempts", "min_edge_psi"}

    retry_patch = next(patch for patch in critique.suggested_changes if patch.field == "max_step_attempts")
    assert retry_patch.old_value == 2
    assert retry_patch.new_value == 1
    assert retry_patch.sample_size == 2
    assert retry_patch.runtime_mode == RuntimeMode.RECOMMEND
    assert retry_patch.policy_version_to == "balanced-1.0.0+patch"

    handoff_patch = next(patch for patch in critique.suggested_changes if patch.field == "min_edge_psi")
    assert handoff_patch.old_value == -0.04
    assert handoff_patch.new_value == 0.0
    assert handoff_patch.sample_size == 1
    assert critique.confidence == 0.66


def test_policy_critic_filters_noop_patch_and_clamps_confidence() -> None:
    policy = get_policy_profile(PolicyName.CONSERVATIVE)
    kernel = _kernel_with_steps(_step(StepState.COMPLETED, 1, 1))
    checkpoints = [SimpleNamespace(risks=("weak_handoffs:x",)) for _ in range(10)]
    outcomes = [SimpleNamespace(decision_quality=1.0) for _ in range(10)]

    critique = PolicyCritic().review(kernel, "wf-noop", policy, checkpoints=checkpoints, outcomes=outcomes)

    assert critique.suggested_changes == ()
    assert critique.findings == ("handoff degraded during checkpoint review",)
    assert critique.confidence == 0.9


def test_quality_gate_passes_and_maps_next_runtime_modes() -> None:
    gate = AdaptiveQualityGate()
    metrics = _metrics()

    observe = gate.evaluate("wf", metrics, RuntimeMode.OBSERVE)
    recommend = gate.evaluate("wf", metrics, RuntimeMode.RECOMMEND)
    controlled = gate.evaluate("wf", metrics, RuntimeMode.CONTROLLED_ADAPTIVE)
    restricted = gate.evaluate("wf", metrics, RuntimeMode.RESTRICTED_CRITICAL)

    assert observe.passed is True
    assert observe.eligible_next_mode == RuntimeMode.RECOMMEND
    assert recommend.eligible_next_mode == RuntimeMode.CONTROLLED_ADAPTIVE
    assert controlled.eligible_next_mode == RuntimeMode.CONTROLLED_ADAPTIVE
    assert restricted.passed is True
    assert restricted.eligible_next_mode is None
    assert observe.violations == ()
    assert observe.warnings == ()
    assert observe.metrics is metrics


def test_quality_gate_reports_every_threshold_violation_and_pending_warning() -> None:
    gate = AdaptiveQualityGate()
    metrics = _metrics(
        outcome_coverage_ratio=0.5,
        policy_patch_success_rate=0.5,
        false_retry_rate=0.5,
        false_reroute_rate=0.5,
        handoff_failure_rate=0.5,
        agent_bloat_ratio=0.5,
        checkpoint_detection_accuracy=0.5,
    )

    report = gate.evaluate(
        "wf-bad",
        metrics,
        RuntimeMode.RECOMMEND,
        pending_outcome_count=3,
        pending_approval_count=2,
        critical=True,
    )

    assert report.passed is False
    assert report.eligible_next_mode is None
    assert report.warnings == ("3 important decisions still need outcomes",)
    assert report.pending_outcome_count == 3
    assert report.pending_approval_count == 2
    assert len(report.violations) == 9
    assert any("outcome coverage 0.50 below 0.95" in item for item in report.violations)
    assert "2 human approval requests are still pending" in report.violations
    assert any("policy patch success rate 0.50 below 0.80" in item for item in report.violations)
    assert "false retry rate 0.50 is too high" in report.violations
    assert "false reroute rate 0.50 is too high" in report.violations
    assert "handoff failure rate 0.50 is too high" in report.violations
    assert "agent bloat ratio 0.50 is too high" in report.violations
    assert any("checkpoint detection accuracy 0.50 below 0.70" in item for item in report.violations)
    assert "critical workflows cannot be promoted to automatic adaptive mode" in report.violations


def test_quality_gate_custom_threshold_boundaries_are_inclusive() -> None:
    gate = AdaptiveQualityGate(
        min_outcome_coverage=0.8,
        min_patch_success_rate=0.7,
        max_false_retry_rate=0.3,
        max_false_reroute_rate=0.4,
        max_handoff_failure_rate=0.5,
        max_agent_bloat_ratio=0.6,
        min_checkpoint_accuracy=0.65,
    )
    metrics = _metrics(
        outcome_coverage_ratio=0.8,
        policy_patch_success_rate=0.7,
        false_retry_rate=0.3,
        false_reroute_rate=0.4,
        handoff_failure_rate=0.5,
        agent_bloat_ratio=0.6,
        checkpoint_detection_accuracy=0.65,
    )

    report = gate.evaluate("wf-boundary", metrics, RuntimeMode.OBSERVE)

    assert report.passed is True
    assert report.violations == ()
    assert report.eligible_next_mode == RuntimeMode.RECOMMEND
