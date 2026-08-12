from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from processual_kernel.adaptive_toolkit import AdaptiveGovernanceToolkit
from processual_kernel.types import MaestroAction


def make_toolkit() -> AdaptiveGovernanceToolkit:
    toolkit = object.__new__(AdaptiveGovernanceToolkit)
    toolkit.kernel = object()
    toolkit.runtime_adapter = Mock()
    toolkit.efficiency_governor = Mock()
    toolkit.authorize_adaptive_action = Mock()
    toolkit.runtime_command_throttle_plan = Mock()
    toolkit._runtime_command_fingerprints = {}
    toolkit._runtime_deduplication_results = {}
    toolkit._runtime_command_results = {}
    toolkit._audit_adaptive = Mock()
    toolkit._persist = Mock()
    return toolkit


def make_report() -> SimpleNamespace:
    return SimpleNamespace(
        workflow_id="wf-1",
        recommended_action=MaestroAction.PAUSE,
        kind=SimpleNamespace(value="scheduled"),
        checkpoint_number=3,
        policy_version="p1",
        risks=("latency",),
        confidence=0.8,
    )


def make_command(*, dry_run: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        workflow_id="wf-1",
        action=MaestroAction.PAUSE,
        subject="wf-1",
        reason="checkpoint recommendation: scheduled",
        payload={"checkpoint_number": 3},
        dry_run=dry_run,
        authorized=True,
        requires_human_approval=False,
        request_id="req-1",
    )


def configure_command(toolkit: AdaptiveGovernanceToolkit, *, dry_run: bool = False) -> SimpleNamespace:
    command = make_command(dry_run=dry_run)
    toolkit.runtime_adapter.build_command.return_value = command
    toolkit.authorize_adaptive_action.return_value = SimpleNamespace(
        authorized=True,
        requires_human_approval=False,
        request_id="req-1",
    )
    toolkit.runtime_adapter.with_authorization.return_value = command
    return command


def test_execute_checkpoint_recommendation_returns_throttle_suppression() -> None:
    toolkit = make_toolkit()
    command = configure_command(toolkit, dry_run=False)
    toolkit.runtime_command_throttle_plan.return_value = SimpleNamespace(suppressed_indices=(0,))

    result = toolkit.execute_checkpoint_recommendation(
        make_report(),
        dry_run=False,
        auto_execute=True,
        throttle_cooldown_seconds=5.0,
    )

    assert result.executed is False
    assert result.reason == "runtime command suppressed by adaptive throttle"
    assert result.action == MaestroAction.PAUSE
    assert toolkit._runtime_command_results["wf-1"] == [result]
    toolkit.runtime_command_throttle_plan.assert_called_once_with(
        "wf-1", (command,), cooldown_seconds=5.0
    )
    toolkit.efficiency_governor.deduplicate_runtime_command.assert_not_called()
    toolkit.runtime_adapter.execute.assert_not_called()
    toolkit._persist.assert_called_once_with("runtime_commands", result)


def test_execute_checkpoint_recommendation_returns_dedupe_suppression() -> None:
    toolkit = make_toolkit()
    command = configure_command(toolkit, dry_run=False)
    dedupe = SimpleNamespace(
        action=MaestroAction.PAUSE,
        duplicate=True,
        suppressed=True,
        reason="duplicate runtime command",
        command_fingerprint="fp-1",
    )
    toolkit.efficiency_governor.deduplicate_runtime_command.return_value = dedupe

    result = toolkit.execute_checkpoint_recommendation(
        make_report(), dry_run=False, auto_execute=True, idempotency_key="idem-1"
    )

    toolkit.efficiency_governor.deduplicate_runtime_command.assert_called_once_with(
        command,
        set(),
        idempotency_key="idem-1",
        prevent_duplicate=True,
    )
    assert result.executed is False
    assert result.reason == "duplicate runtime command"
    assert result.event_payload == {"command_fingerprint": "fp-1"}
    assert toolkit._runtime_deduplication_results["wf-1"] == [dedupe]
    toolkit.runtime_adapter.execute.assert_not_called()
    assert toolkit._persist.call_args_list[0].args == ("runtime_command_deduplication", dedupe)
    assert toolkit._persist.call_args_list[1].args == ("runtime_commands", result)


def test_execute_checkpoint_recommendation_executes_and_tracks_fingerprint() -> None:
    toolkit = make_toolkit()
    command = configure_command(toolkit, dry_run=False)
    dedupe = SimpleNamespace(
        action=MaestroAction.PAUSE,
        duplicate=False,
        suppressed=False,
        reason="unique runtime command",
        command_fingerprint="fp-2",
    )
    executed = SimpleNamespace(
        workflow_id="wf-1",
        action=MaestroAction.PAUSE,
        executed=True,
        dry_run=False,
        authorized=True,
        requires_human_approval=False,
        request_id="req-1",
    )
    toolkit.efficiency_governor.deduplicate_runtime_command.return_value = dedupe
    toolkit.runtime_adapter.execute.return_value = executed

    result = toolkit.execute_checkpoint_recommendation(make_report(), dry_run=False, auto_execute=True)

    assert result is executed
    toolkit.runtime_adapter.execute.assert_called_once_with(toolkit.kernel, command)
    assert toolkit._runtime_command_fingerprints["wf-1"] == {"fp-2"}
    assert toolkit._runtime_command_results["wf-1"] == [executed]


def test_execute_checkpoint_recommendation_forces_dry_run_without_auto_execute() -> None:
    toolkit = make_toolkit()
    configure_command(toolkit, dry_run=True)
    dedupe = SimpleNamespace(
        action=MaestroAction.PAUSE,
        duplicate=False,
        suppressed=False,
        reason="unique runtime command",
        command_fingerprint="fp-dry",
    )
    dry_result = SimpleNamespace(
        workflow_id="wf-1",
        action=MaestroAction.PAUSE,
        executed=False,
        dry_run=True,
        authorized=True,
        requires_human_approval=False,
        request_id="req-1",
    )
    toolkit.efficiency_governor.deduplicate_runtime_command.return_value = dedupe
    toolkit.runtime_adapter.execute.return_value = dry_result

    result = toolkit.execute_checkpoint_recommendation(make_report(), dry_run=False, auto_execute=False)

    assert result is dry_result
    kwargs = toolkit.runtime_adapter.build_command.call_args.kwargs
    assert kwargs["dry_run"] is True
    assert toolkit._runtime_command_fingerprints["wf-1"] == set()
