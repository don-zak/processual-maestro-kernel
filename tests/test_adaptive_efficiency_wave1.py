from types import SimpleNamespace

from processual_kernel.adaptive.efficiency import AdaptiveEfficiencyGovernor, _safe_dict
from processual_kernel.adaptive_types import CheckpointKind, CheckpointScheduleDecision, RuntimeCommand
from processual_kernel.types import MaestroAction


def _command(
    action: MaestroAction = MaestroAction.RETRY,
    *,
    subject: str = "agent-1",
    dry_run: bool = False,
    payload: dict | None = None,
) -> RuntimeCommand:
    return RuntimeCommand(
        workflow_id="wf-1",
        action=action,
        subject=subject,
        reason="coverage-wave-1",
        payload={} if payload is None else payload,
        dry_run=dry_run,
    )


def _decision(
    *,
    due: bool = True,
    trigger: CheckpointKind | None = CheckpointKind.HOURLY,
    event: str | None = "heartbeat",
    final: bool = False,
    created_at: float = 100.0,
    next_due_at: float | None = None,
) -> CheckpointScheduleDecision:
    return CheckpointScheduleDecision(
        workflow_id="wf-1",
        due=due,
        trigger=trigger,
        reason="scheduled",
        event=event,
        final=final,
        created_at=created_at,
        next_due_at=next_due_at,
    )


def test_safe_dict_normalizes_nested_supported_values() -> None:
    command = _command(dry_run=True, payload={"items": (MaestroAction.RETRY, [MaestroAction.PAUSE])})

    normalized = _safe_dict(
        {
            "command": command,
            "tuple": (MaestroAction.RETRY,),
            "list": [MaestroAction.PAUSE],
            7: {"action": MaestroAction.OBSERVE},
        }
    )

    assert normalized["command"]["action"] == MaestroAction.RETRY
    assert normalized["tuple"] == ["retry"]
    assert normalized["list"] == ["pause"]
    assert normalized["7"]["action"] == "observe"
    assert _safe_dict("unchanged") == "unchanged"


def test_command_fingerprint_is_stable_and_supports_explicit_idempotency() -> None:
    governor = AdaptiveEfficiencyGovernor()
    command = _command(payload={"b": 2, "a": 1})
    equivalent = _command(payload={"a": 1, "b": 2})

    assert governor.command_fingerprint(command) == governor.command_fingerprint(equivalent)
    assert governor.command_fingerprint(command, idempotency_key="abc") == "explicit:abc"
    assert governor.command_fingerprint(command) != governor.command_fingerprint(
        _command(payload={"a": 1, "b": 3})
    )


def test_checkpoint_coalescing_disabled_or_not_applicable() -> None:
    governor = AdaptiveEfficiencyGovernor()
    decision = _decision()

    no_previous = governor.coalesce_checkpoint_decision(decision, cooldown_seconds=30)
    disabled = governor.coalesce_checkpoint_decision(decision, decision, cooldown_seconds=0)
    not_due = governor.coalesce_checkpoint_decision(_decision(due=False), decision, cooldown_seconds=30)

    assert not no_previous.coalesced
    assert not disabled.coalesced
    assert not not_due.coalesced
    assert no_previous.effective_decision is decision


def test_checkpoint_coalescing_preserves_final_and_critical_events() -> None:
    governor = AdaptiveEfficiencyGovernor()
    previous = _decision(created_at=90)

    final = governor.coalesce_checkpoint_decision(
        _decision(trigger=CheckpointKind.FINAL, final=True),
        previous,
        cooldown_seconds=30,
    )
    critical = governor.coalesce_checkpoint_decision(
        _decision(event="critical_agent_failure"),
        previous,
        cooldown_seconds=30,
    )

    assert not final.coalesced
    assert not critical.coalesced
    assert "never coalesced" in final.reason
    assert "never coalesced" in critical.reason


def test_checkpoint_coalescing_requires_previous_due_and_matching_signal() -> None:
    governor = AdaptiveEfficiencyGovernor()
    decision = _decision(created_at=100)

    previous_not_due = governor.coalesce_checkpoint_decision(
        decision,
        _decision(due=False, created_at=90),
        cooldown_seconds=30,
    )
    distinct = governor.coalesce_checkpoint_decision(
        decision,
        _decision(event="different", created_at=90),
        cooldown_seconds=30,
    )

    assert not previous_not_due.coalesced
    assert "previous checkpoint" in previous_not_due.reason
    assert not distinct.coalesced
    assert "distinct" in distinct.reason


def test_checkpoint_coalescing_suppresses_duplicate_within_window() -> None:
    governor = AdaptiveEfficiencyGovernor()
    result = governor.coalesce_checkpoint_decision(
        _decision(created_at=100),
        _decision(created_at=90),
        cooldown_seconds=30,
    )

    assert result.coalesced
    assert not result.effective_decision.due
    assert result.effective_decision.trigger == CheckpointKind.HOURLY
    assert "30s cooldown" in result.reason


def test_runtime_command_deduplication_distinguishes_mutation_and_dry_run() -> None:
    governor = AdaptiveEfficiencyGovernor()
    mutating = _command()
    fingerprint = governor.command_fingerprint(mutating)

    duplicate = governor.deduplicate_runtime_command(mutating, {fingerprint})
    allowed_duplicate = governor.deduplicate_runtime_command(
        mutating,
        {fingerprint},
        prevent_duplicate=False,
    )
    dry_run = governor.deduplicate_runtime_command(_command(dry_run=True), {fingerprint})

    assert duplicate.duplicate and duplicate.suppressed
    assert not allowed_duplicate.duplicate
    assert not dry_run.duplicate
    assert "dry-run" in dry_run.reason


def test_checkpoint_backpressure_handles_protected_coalesced_and_future_cases() -> None:
    governor = AdaptiveEfficiencyGovernor()
    final = governor.checkpoint_backpressure_hint(_decision(final=True), now=100)
    critical = governor.checkpoint_backpressure_hint(_decision(event="human_escalation"), now=100)

    original = _decision(created_at=100)
    coalescing = governor.coalesce_checkpoint_decision(
        original,
        _decision(created_at=95),
        cooldown_seconds=60,
    )
    coalesced = governor.checkpoint_backpressure_hint(original, coalescing, now=100)
    future = governor.checkpoint_backpressure_hint(
        _decision(due=False, next_due_at=180),
        now=100,
        min_poll_seconds=5,
        max_poll_seconds=60,
    )

    assert not final.active and final.recommended_delay_seconds == 0
    assert not critical.active and critical.recommended_delay_seconds == 0
    assert coalesced.active and coalesced.recommended_delay_seconds == 60
    assert future.active and future.recommended_delay_seconds == 60
    assert future.next_safe_check_at == 160


def test_checkpoint_backpressure_allows_actionable_or_idle_signals() -> None:
    governor = AdaptiveEfficiencyGovernor()

    due = governor.checkpoint_backpressure_hint(_decision(due=True), now=100)
    idle = governor.checkpoint_backpressure_hint(_decision(due=False, next_due_at=None), now=100)

    assert not due.active
    assert "actionable" in due.reason
    assert not idle.active
    assert "no checkpoint backpressure" in idle.reason


def test_runtime_command_batch_enforces_dedupe_and_mutation_limit() -> None:
    governor = AdaptiveEfficiencyGovernor()
    duplicate = _command(subject="a")
    allowed = _command(subject="b")
    over_limit = _command(subject="c")
    dry_run = _command(subject="d", dry_run=True)
    duplicate_key = governor.command_fingerprint(duplicate)

    plan = governor.plan_runtime_command_batch(
        "wf-1",
        [duplicate, allowed, over_limit, dry_run],
        {duplicate_key},
        max_mutating_commands=1,
    )

    assert plan.input_count == 4
    assert plan.allowed_count == 2
    assert plan.suppressed_count == 2
    assert any("duplicate" in reason for reason in plan.reasons)
    assert any("batch limit" in reason for reason in plan.reasons)


def test_runtime_command_batch_accepts_clean_batch_and_explicit_keys() -> None:
    governor = AdaptiveEfficiencyGovernor()

    plan = governor.plan_runtime_command_batch(
        "wf-1",
        [_command(subject="a"), _command(subject="b", dry_run=True)],
        set(),
        max_mutating_commands=2,
        idempotency_keys=["one", None],
    )

    assert plan.allowed_count == 2
    assert plan.suppressed_count == 0
    assert plan.fingerprints[0] == "explicit:one"
    assert plan.reasons == ("runtime command batch is within dedupe and mutating limits",)


def test_runtime_command_conflicts_keep_highest_priority_per_subject() -> None:
    governor = AdaptiveEfficiencyGovernor()
    commands = [
        _command(MaestroAction.RETRY, subject="same"),
        _command(MaestroAction.ESCALATE, subject="same"),
        _command(MaestroAction.PAUSE, subject="other"),
        _command(MaestroAction.OBSERVE, subject="same", dry_run=True),
    ]

    plan = governor.plan_runtime_command_conflicts("wf-1", commands)

    assert plan.allowed_indices == (1, 2, 3)
    assert plan.suppressed_indices == (0,)
    assert plan.primary_action == MaestroAction.ESCALATE
    assert plan.conflicting_count == 1


def test_runtime_command_conflicts_can_treat_all_subjects_as_one_group() -> None:
    governor = AdaptiveEfficiencyGovernor()

    plan = governor.plan_runtime_command_conflicts(
        "wf-1",
        [_command(MaestroAction.RETRY, subject="a"), _command(MaestroAction.PAUSE, subject="b")],
        protect_subjects=False,
    )

    assert plan.allowed_indices == (1,)
    assert plan.suppressed_indices == (0,)
    assert plan.primary_action == MaestroAction.PAUSE


def test_runtime_command_throttle_covers_dry_run_protected_disabled_and_recent() -> None:
    governor = AdaptiveEfficiencyGovernor()
    recent = SimpleNamespace(
        action=MaestroAction.RETRY,
        subject="agent-1",
        created_at=95.0,
        event_payload={},
        workflow_id="wf-1",
    )

    plan = governor.plan_runtime_command_throttle(
        "wf-1",
        [
            _command(MaestroAction.RETRY, subject="agent-1"),
            _command(MaestroAction.ESCALATE, subject="agent-2"),
            _command(MaestroAction.PAUSE, subject="agent-3", dry_run=True),
        ],
        recent_commands=[recent],
        cooldown_seconds=30,
        now=100,
    )

    assert plan.allowed_indices == (1, 2)
    assert plan.suppressed_indices == (0,)
    assert MaestroAction.ESCALATE in plan.protected_actions
    assert any("throttle" in reason for reason in plan.reasons)

    disabled = governor.plan_runtime_command_throttle(
        "wf-1",
        [_command(MaestroAction.RETRY)],
        cooldown_seconds=0,
        now=100,
    )
    empty = governor.plan_runtime_command_throttle("wf-1", [], cooldown_seconds=30, now=100)

    assert disabled.allowed_indices == (0,)
    assert empty.reasons == ("no runtime commands to throttle",)
