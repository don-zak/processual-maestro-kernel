from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.types import KernelPolicy


def make_toolkit() -> tuple[AdaptiveGovernanceToolkit, SimpleNamespace]:
    kernel = SimpleNamespace(
        policy=KernelPolicy(),
        governor=SimpleNamespace(policy=None),
        _audit=Mock(),
        get_workflow=Mock(),
    )
    toolkit = AdaptiveGovernanceToolkit(kernel)
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    toolkit.efficiency_governor = Mock()
    return toolkit, kernel


def test_checkpoint_schedule_decision_tracks_effective_coalescing_and_backpressure() -> None:
    toolkit, _ = make_toolkit()
    profile = object()
    policy = object()
    original = SimpleNamespace(due=True, trigger=SimpleNamespace(value="interval"), reason="checkpoint due")
    effective = SimpleNamespace(due=False, trigger=None, reason="coalesced")
    coalescing = SimpleNamespace(
        original_decision=original,
        effective_decision=effective,
        coalesced=True,
        reason="cooldown",
        cooldown_seconds=45.0,
    )
    backpressure = SimpleNamespace(active=True, recommended_delay_seconds=15.0, reason="recent checkpoint")
    toolkit.checkpoints = SimpleNamespace(_last_checkpoint_at={"wf-1": 12.0})
    toolkit.checkpoint_controller = Mock()
    toolkit.checkpoint_controller.inspect.return_value = original
    toolkit.efficiency_governor.coalesce_checkpoint_decision.return_value = coalescing
    toolkit.efficiency_governor.checkpoint_backpressure_hint.return_value = backpressure

    result = toolkit.checkpoint_schedule_decision(
        "wf-1",
        profile=profile,
        policy=policy,
        event="step_completed",
        milestone=True,
        now=20.0,
        coalesce_window_seconds=45.0,
    )

    assert result is effective
    toolkit.checkpoint_controller.inspect.assert_called_once_with(
        "wf-1",
        profile,
        policy,
        last_checkpoint_at=12.0,
        event="step_completed",
        milestone=True,
        final=False,
        now=20.0,
    )
    toolkit.efficiency_governor.coalesce_checkpoint_decision.assert_called_once_with(
        original,
        previous_decision=None,
        cooldown_seconds=45.0,
    )
    toolkit.efficiency_governor.checkpoint_backpressure_hint.assert_called_once_with(
        effective,
        coalescing,
        now=20.0,
        max_poll_seconds=45.0,
    )
    assert toolkit._checkpoint_schedule_decisions["wf-1"] == [effective]
    assert toolkit._checkpoint_coalescing_decisions["wf-1"] == [coalescing]
    assert toolkit._checkpoint_backpressure_hints["wf-1"] == [backpressure]
    assert toolkit._audit_adaptive.call_count == 3
    assert [call.args[0].value for call in toolkit._audit_adaptive.call_args_list] == [
        "checkpoint_schedule_decision",
        "checkpoint_coalescing_decision",
        "checkpoint_backpressure_hint",
    ]
    assert [call.args[0] for call in toolkit._persist.call_args_list] == [
        "checkpoint_schedule_decisions",
        "checkpoint_coalescing_decisions",
        "checkpoint_backpressure_hints",
    ]


def test_checkpoint_schedule_reuses_previous_original_decision_and_cached_context() -> None:
    toolkit, kernel = make_toolkit()
    profile = object()
    policy = object()
    previous_original = object()
    previous_coalescing = SimpleNamespace(original_decision=previous_original)
    original = SimpleNamespace(due=True, trigger=SimpleNamespace(value="event"), reason="event")
    effective = SimpleNamespace(due=True, trigger=SimpleNamespace(value="event"), reason="event")
    coalescing = SimpleNamespace(
        original_decision=original,
        effective_decision=effective,
        coalesced=False,
        reason="not coalesced",
        cooldown_seconds=0.0,
    )
    backpressure = SimpleNamespace(active=False, recommended_delay_seconds=0.0, reason="none")
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = policy
    toolkit._checkpoint_coalescing_decisions["wf-1"] = [previous_coalescing]
    toolkit.checkpoints = SimpleNamespace(_last_checkpoint_at={})
    toolkit.checkpoint_controller = Mock()
    toolkit.checkpoint_controller.inspect.return_value = original
    toolkit.efficiency_governor.coalesce_checkpoint_decision.return_value = coalescing
    toolkit.efficiency_governor.checkpoint_backpressure_hint.return_value = backpressure

    assert toolkit.checkpoint_schedule_decision("wf-1", final=True, coalesce_window_seconds=0.0) is effective

    kernel.get_workflow.assert_not_called()
    toolkit.efficiency_governor.coalesce_checkpoint_decision.assert_called_once_with(
        original,
        previous_decision=previous_original,
        cooldown_seconds=0.0,
    )
    toolkit.efficiency_governor.checkpoint_backpressure_hint.assert_called_once_with(
        effective,
        coalescing,
        now=None,
        max_poll_seconds=30.0,
    )


def test_runtime_command_batch_and_conflict_plans_are_recorded_audited_and_persisted() -> None:
    toolkit, _ = make_toolkit()
    commands = (object(), object())
    batch = SimpleNamespace(input_count=2, allowed_count=1, suppressed_count=1)
    conflict = SimpleNamespace(
        input_count=2,
        conflicting_count=1,
        suppressed_indices=(1,),
        primary_action=SimpleNamespace(value="pause"),
    )
    toolkit.efficiency_governor.plan_runtime_command_batch.return_value = batch
    toolkit.efficiency_governor.plan_runtime_command_conflicts.return_value = conflict

    assert toolkit.runtime_command_batch_plan(
        "wf-1",
        commands,
        max_mutating_commands=2,
        prevent_duplicate=False,
        idempotency_keys=("a", "b"),
    ) is batch
    seen = toolkit._runtime_command_fingerprints["wf-1"]
    toolkit.efficiency_governor.plan_runtime_command_batch.assert_called_once_with(
        "wf-1",
        commands,
        seen,
        max_mutating_commands=2,
        prevent_duplicate=False,
        idempotency_keys=("a", "b"),
    )
    assert toolkit._runtime_batch_plans["wf-1"] == [batch]

    assert toolkit.runtime_command_conflict_plan("wf-1", commands, protect_subjects=False) is conflict
    toolkit.efficiency_governor.plan_runtime_command_conflicts.assert_called_once_with(
        "wf-1",
        commands,
        protect_subjects=False,
    )
    assert toolkit._runtime_conflict_plans["wf-1"] == [conflict]
    assert toolkit._audit_adaptive.call_count == 2
    assert toolkit._persist.call_args_list[0].args == ("runtime_command_batch_plans", batch)
    assert toolkit._persist.call_args_list[1].args == ("runtime_command_conflict_plans", conflict)


def test_runtime_command_throttle_uses_recorded_results_by_default() -> None:
    toolkit, _ = make_toolkit()
    command = object()
    prior = object()
    plan = SimpleNamespace(input_count=1, suppressed_indices=(0,), cooldown_seconds=8.0)
    toolkit._runtime_command_results["wf-1"] = [prior]
    toolkit.efficiency_governor.plan_runtime_command_throttle.return_value = plan

    assert toolkit.runtime_command_throttle_plan(
        "wf-1",
        (command,),
        cooldown_seconds=8.0,
        now=100.0,
    ) is plan

    toolkit.efficiency_governor.plan_runtime_command_throttle.assert_called_once_with(
        "wf-1",
        (command,),
        recent_commands=(prior,),
        cooldown_seconds=8.0,
        now=100.0,
    )
    assert toolkit._runtime_throttle_plans["wf-1"] == [plan]
    assert toolkit._persist.call_args.args == ("runtime_command_throttle_plans", plan)


def test_adaptive_workload_budget_counts_only_prior_allowed_matching_operation() -> None:
    toolkit, _ = make_toolkit()
    toolkit._workload_budget_decisions["wf-1"] = [
        SimpleNamespace(operation="replay", allowed=True, cost_units=2),
        SimpleNamespace(operation="replay", allowed=False, cost_units=7),
        SimpleNamespace(operation="export", allowed=True, cost_units=5),
    ]
    decision = SimpleNamespace(
        operation="replay",
        allowed=True,
        used_count=2,
        limit=6,
        cost_units=3,
        reason="within budget",
    )
    toolkit.efficiency_governor.workload_budget_decision.return_value = decision

    assert toolkit.adaptive_workload_budget_decision("wf-1", "replay", limit=6, cost_units=3) is decision

    toolkit.efficiency_governor.workload_budget_decision.assert_called_once_with(
        "wf-1",
        "replay",
        used_count=2,
        limit=6,
        cost_units=3,
    )
    assert toolkit._workload_budget_decisions["wf-1"][-1] is decision
    payload = toolkit._audit_adaptive.call_args.args[2]
    assert payload["allowed"] is True
    assert payload["used_count"] == 2
    assert payload["cost_units"] == 3
    assert toolkit._persist.call_args.args == ("workload_budget_decisions", decision)
