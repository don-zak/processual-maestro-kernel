from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = Mock()
    toolkit.profile_task = Mock()
    toolkit.select_policy = Mock()
    toolkit.checkpoint_schedule_decision = Mock()
    toolkit.checkpoints = Mock()
    toolkit._profiles = {}
    toolkit._policies = {}
    toolkit._checkpoint_reports = {}
    toolkit._audit_adaptive = Mock()
    toolkit._analyze_checkpoint = Mock()
    toolkit.history_recorder = Mock()
    toolkit._record_history_event = Mock()
    toolkit._persist = Mock()
    return toolkit


def test_maybe_checkpoint_uses_supplied_profile_and_policy_without_coalescing() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(policy_version="p1")
    toolkit.checkpoints.maybe_checkpoint.return_value = None

    report = toolkit.maybe_checkpoint(
        "wf-1",
        profile=profile,
        policy=policy,
        event="step_completed",
        milestone=True,
        final=False,
        now=123.0,
    )

    assert report is None
    toolkit.profile_task.assert_not_called()
    toolkit.select_policy.assert_not_called()
    toolkit.checkpoint_schedule_decision.assert_not_called()
    toolkit.checkpoints.maybe_checkpoint.assert_called_once_with(
        toolkit.kernel,
        "wf-1",
        profile,
        policy,
        event="step_completed",
        milestone=True,
        final=False,
        now=123.0,
    )
    toolkit._persist.assert_not_called()


def test_maybe_checkpoint_uses_cached_profile_and_policy() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="cached-profile")
    policy = SimpleNamespace(policy_version="cached-policy")
    toolkit._profiles["wf-1"] = profile
    toolkit._policies["wf-1"] = policy
    toolkit.checkpoints.maybe_checkpoint.return_value = None

    toolkit.maybe_checkpoint("wf-1", now=10.0)

    toolkit.kernel.get_workflow.assert_not_called()
    toolkit.profile_task.assert_not_called()
    toolkit.select_policy.assert_not_called()
    toolkit.checkpoints.maybe_checkpoint.assert_called_once_with(
        toolkit.kernel,
        "wf-1",
        profile,
        policy,
        event=None,
        milestone=False,
        final=False,
        now=10.0,
    )


def test_maybe_checkpoint_profiles_workflow_and_selects_policy_when_missing() -> None:
    toolkit = make_toolkit()
    workflow = SimpleNamespace(workflow_id="wf-1")
    profile = SimpleNamespace(name="generated-profile")
    policy = SimpleNamespace(policy_version="generated-policy")
    toolkit.kernel.get_workflow.return_value = workflow
    toolkit.profile_task.return_value = profile
    toolkit.select_policy.return_value = policy
    toolkit.checkpoints.maybe_checkpoint.return_value = None

    toolkit.maybe_checkpoint("wf-1")

    toolkit.kernel.get_workflow.assert_called_once_with("wf-1")
    toolkit.profile_task.assert_called_once_with(workflow)
    toolkit.select_policy.assert_called_once_with(profile, workflow_id="wf-1")
    toolkit.checkpoints.maybe_checkpoint.assert_called_once_with(
        toolkit.kernel,
        "wf-1",
        profile,
        policy,
        event=None,
        milestone=False,
        final=False,
        now=None,
    )


def test_maybe_checkpoint_stops_when_coalesced_schedule_is_not_due() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(policy_version="p1")
    toolkit.checkpoint_schedule_decision.return_value = SimpleNamespace(due=False)

    report = toolkit.maybe_checkpoint(
        "wf-1",
        profile=profile,
        policy=policy,
        event="heartbeat",
        now=25.0,
        coalesce_window_seconds=30.0,
    )

    assert report is None
    toolkit.checkpoint_schedule_decision.assert_called_once_with(
        "wf-1",
        profile=profile,
        policy=policy,
        event="heartbeat",
        milestone=False,
        final=False,
        now=25.0,
        coalesce_window_seconds=30.0,
    )
    toolkit.checkpoints.maybe_checkpoint.assert_not_called()
    toolkit._audit_adaptive.assert_not_called()
    toolkit._persist.assert_not_called()


def test_maybe_checkpoint_records_generated_report_and_history() -> None:
    toolkit = make_toolkit()
    profile = SimpleNamespace(name="profile")
    policy = SimpleNamespace(policy_version="p7")
    report = SimpleNamespace(
        workflow_id="wf-1",
        policy_version="p7",
        checkpoint_number=3,
        kind=SimpleNamespace(value="milestone"),
        recommended_action=SimpleNamespace(value="continue"),
        confidence=0.91,
    )
    history_one = SimpleNamespace(event_id="h1")
    history_two = SimpleNamespace(event_id="h2")
    toolkit.checkpoint_schedule_decision.return_value = SimpleNamespace(due=True)
    toolkit.checkpoints.maybe_checkpoint.return_value = report
    toolkit.history_recorder.record_checkpoint.return_value = (history_one, history_two)

    result = toolkit.maybe_checkpoint(
        "wf-1",
        profile=profile,
        policy=policy,
        event="milestone",
        milestone=True,
        final=False,
        now=50.0,
        coalesce_window_seconds=15.0,
    )

    assert result is report
    assert toolkit._checkpoint_reports["wf-1"] == [report]
    toolkit.checkpoint_schedule_decision.assert_called_once_with(
        "wf-1",
        profile=profile,
        policy=policy,
        event="milestone",
        milestone=True,
        final=False,
        now=50.0,
        coalesce_window_seconds=15.0,
    )
    toolkit.checkpoints.maybe_checkpoint.assert_called_once_with(
        toolkit.kernel,
        "wf-1",
        profile,
        policy,
        event="milestone",
        milestone=True,
        final=False,
        now=50.0,
    )
    toolkit._analyze_checkpoint.assert_called_once_with(report, profile, policy)
    toolkit.history_recorder.record_checkpoint.assert_called_once_with(report)
    assert toolkit._record_history_event.call_args_list == [call(history_one), call(history_two)]
    toolkit._persist.assert_called_once_with("checkpoints", report)
    audit_payload = toolkit._audit_adaptive.call_args.args[2]
    assert audit_payload["workflow_id"] == "wf-1"
    assert audit_payload["policy_version"] == "p7"
    assert audit_payload["checkpoint_number"] == 3
    assert audit_payload["kind"] == "milestone"
    assert audit_payload["recommended_action"] == "continue"
    assert audit_payload["confidence"] == 0.91
    assert audit_payload["payload"] is report
