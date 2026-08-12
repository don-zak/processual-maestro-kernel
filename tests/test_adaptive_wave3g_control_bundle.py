from __future__ import annotations

import pytest

from processual_kernel.adaptive.calibrator import CalibrationEngine
from processual_kernel.adaptive.checkpoint_controller import CheckpointScheduleController
from processual_kernel.adaptive.drift_detector import DriftDetector
from processual_kernel.adaptive_types import (
    AgentCountBand,
    AmbiguityLevel,
    CheckpointKind,
    PolicyName,
    PolicyPatch,
    PolicyProfile,
    RiskLevel,
    RuntimeMode,
    TaskDuration,
    TaskProfile,
    TaskSize,
)
from processual_kernel.types import KernelPolicy


def _profile(duration: TaskDuration = TaskDuration.LONG) -> TaskProfile:
    return TaskProfile(
        size=TaskSize.MEDIUM,
        duration=duration,
        risk=RiskLevel.LOW,
        ambiguity=AmbiguityLevel.MEDIUM,
        agent_count=AgentCountBand.FEW,
        requires_audit=True,
    )


def _policy(interval: int | None = 60) -> PolicyProfile:
    return PolicyProfile(
        name=PolicyName.BALANCED,
        policy_version="test-1",
        kernel_policy=KernelPolicy(),
        checkpoint_interval_minutes=interval,
        runtime_mode=RuntimeMode.RECOMMEND,
        max_agents=4,
        max_retries=2,
        parallel_execution=True,
        drift_sensitivity=0.2,
        min_sample_size=3,
        human_gate_required=False,
    )


def _patch(
    *,
    field: str = "min_edge_psi",
    old_value=-0.05,
    new_value=0.05,
    sample_size: int = 20,
    reversible: bool = True,
) -> PolicyPatch:
    return PolicyPatch(
        field=field,
        old_value=old_value,
        new_value=new_value,
        reason="coverage test",
        policy_version_from="test-1",
        policy_version_to="test-2",
        sample_size=sample_size,
        reversible=reversible,
    )


def test_calibration_safety_gates_cover_fields_samples_reversibility_and_ranges() -> None:
    assert CalibrationEngine._is_safe(_patch(), 20) is True
    assert CalibrationEngine._is_safe(_patch(field="dt", old_value=0.1, new_value=0.11), 20) is False
    assert CalibrationEngine._is_safe(_patch(field="unknown", old_value=1, new_value=2), 20) is False
    assert CalibrationEngine._is_safe(_patch(sample_size=19), 20) is False
    assert CalibrationEngine._is_safe(_patch(reversible=False), 20) is False
    assert CalibrationEngine._is_safe(_patch(new_value=0.5), 20) is False
    assert (
        CalibrationEngine._is_safe(
            _patch(field="quarantine_policy_risk", old_value=0.5, new_value=1.1),
            20,
        )
        is False
    )
    assert (
        CalibrationEngine._is_safe(
            _patch(field="archive_max_psi", old_value=0.0, new_value=1.1),
            20,
        )
        is False
    )


def test_calibration_max_step_attempts_and_non_numeric_small_change_rules() -> None:
    assert CalibrationEngine._is_small_change("max_step_attempts", 2, 3) is True
    assert CalibrationEngine._is_small_change("max_step_attempts", 2, 4) is False
    assert CalibrationEngine._is_small_change("max_step_attempts", 1, 0) is False
    assert CalibrationEngine._is_small_change("max_step_attempts", 5, 6) is False
    assert CalibrationEngine._is_small_change("max_step_attempts", 2.0, 3) is False
    assert CalibrationEngine._is_small_change("custom", "a", "b") is True
    assert CalibrationEngine._is_small_change("custom", "a", "a") is False


def test_calibration_apply_requires_controlled_mode_and_safe_patch() -> None:
    policy = KernelPolicy(min_edge_psi=-0.05, policy_version="test-1")
    patch = _patch()

    recommend = CalibrationEngine(mode=RuntimeMode.RECOMMEND)
    with pytest.raises(RuntimeError, match="controlled adaptive mode"):
        recommend.apply_patch(policy, patch)

    controlled = CalibrationEngine(mode=RuntimeMode.CONTROLLED_ADAPTIVE, min_sample_size=20)
    updated = controlled.apply_patch(policy, patch)
    assert updated.min_edge_psi == 0.05
    assert updated.policy_version == "test-2"
    assert controlled.applied_patches[-1].runtime_mode == RuntimeMode.CONTROLLED_ADAPTIVE

    with pytest.raises(ValueError, match="unsafe or forbidden patch"):
        controlled.apply_patch(policy, _patch(sample_size=1))


def test_calibration_rollback_restores_value_and_rejects_unsafe_cases() -> None:
    engine = CalibrationEngine(mode=RuntimeMode.CONTROLLED_ADAPTIVE)
    policy = KernelPolicy(min_edge_psi=0.05, policy_version="test-2")
    patch = _patch()

    rolled_back = engine.rollback_patch(policy, patch)
    assert rolled_back.min_edge_psi == -0.05
    assert rolled_back.policy_version == "test-1+rollback"
    assert engine.rollback_history[-1].runtime_mode == RuntimeMode.CONTROLLED_ADAPTIVE

    with pytest.raises(ValueError, match="irreversible"):
        engine.rollback_patch(policy, _patch(reversible=False))
    with pytest.raises(ValueError, match="unsafe or forbidden rollback field"):
        engine.rollback_patch(policy, _patch(field="dt", old_value=0.1, new_value=0.11))


def test_checkpoint_controller_precedence_final_event_and_milestone() -> None:
    controller = CheckpointScheduleController()
    profile = _profile()
    policy = _policy(60)

    final = controller.inspect(
        "wf",
        profile,
        policy,
        last_checkpoint_at=100.0,
        event="repeated_failure",
        milestone=True,
        final=True,
        now=120.0,
    )
    assert final.due is True
    assert final.trigger == CheckpointKind.FINAL
    assert final.next_due_at == 3700.0

    event = controller.inspect("wf", profile, policy, event="repeated_failure", milestone=True, now=120.0)
    assert event.due is True
    assert event.trigger == CheckpointKind.EVENT_BASED
    assert "risk event detected" in event.reason

    milestone = controller.inspect("wf", profile, policy, milestone=True, now=120.0)
    assert milestone.due is True
    assert milestone.trigger == CheckpointKind.MILESTONE


def test_checkpoint_controller_periodic_schedule_branches() -> None:
    controller = CheckpointScheduleController()
    profile = _profile()

    disabled = controller.inspect("wf", profile, _policy(None), now=100.0)
    assert disabled.due is False
    assert disabled.trigger is None
    assert disabled.next_due_at is None

    first = controller.inspect("wf", profile, _policy(60), now=100.0)
    assert first.due is True
    assert first.trigger == CheckpointKind.HOURLY
    assert first.next_due_at == 3700.0

    elapsed_hourly = controller.inspect(
        "wf",
        profile,
        _policy(60),
        last_checkpoint_at=100.0,
        now=3700.0,
    )
    assert elapsed_hourly.due is True
    assert elapsed_hourly.trigger == CheckpointKind.HOURLY

    elapsed_short_interval = controller.inspect(
        "wf",
        profile,
        _policy(15),
        last_checkpoint_at=100.0,
        now=1000.0,
    )
    assert elapsed_short_interval.due is True
    assert elapsed_short_interval.trigger == CheckpointKind.MILESTONE

    waiting = controller.inspect(
        "wf",
        profile,
        _policy(60),
        last_checkpoint_at=100.0,
        now=200.0,
    )
    assert waiting.due is False
    assert waiting.trigger is None
    assert waiting.next_due_at == 3700.0


def test_drift_detector_requires_full_window_and_ignores_small_declines() -> None:
    detector = DriftDetector(window=1, sensitivity=0.15)
    assert detector.window == 2
    assert detector.observe("agent", "agent", "quality", 1.0) is None
    assert detector.observe("agent", "agent", "quality", 0.9) is None


def test_drift_detector_emits_medium_and_high_alerts() -> None:
    medium = DriftDetector(window=3, sensitivity=0.15)
    assert medium.observe("a", "agent", "quality", 1.0) is None
    assert medium.observe("a", "agent", "quality", 0.95) is None
    alert = medium.observe("a", "agent", "quality", 0.8)
    assert alert is not None
    assert alert.previous_value == 1.0
    assert alert.current_value == 0.8
    assert alert.severity == RiskLevel.MEDIUM
    assert "declined by 0.200" in alert.reason

    high = DriftDetector(window=3, sensitivity=0.1)
    high.observe("a", "agent", "quality", 1.0)
    high.observe("a", "agent", "quality", 0.9)
    alert = high.observe("a", "agent", "quality", 0.7)
    assert alert is not None
    assert alert.severity == RiskLevel.HIGH


def test_drift_detector_tracks_metrics_independently() -> None:
    detector = DriftDetector(window=2, sensitivity=0.1)
    assert detector.observe("a", "agent", "quality", 1.0) is None
    assert detector.observe("a", "agent", "latency", 1.0) is None

    quality = detector.observe("a", "agent", "quality", 0.7)
    latency = detector.observe("a", "agent", "latency", 1.2)

    assert quality is not None
    assert quality.metric == "quality"
    assert latency is None
