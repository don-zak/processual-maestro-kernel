from __future__ import annotations

import time

from ..adaptive_types import CheckpointKind, CheckpointScheduleDecision, PolicyProfile, TaskDuration, TaskProfile
from .checkpoints import RISK_EVENTS


class CheckpointScheduleController:
    """Read-only checkpoint due checker.

    Unlike CheckpointScheduler.maybe_checkpoint(), this class performs no mutation and creates no checkpoint report.
    It lets host runtimes ask, "is a checkpoint due?" before spending work on a full adaptive cycle.
    """

    def inspect(
        self,
        workflow_id: str,
        profile: TaskProfile,
        policy: PolicyProfile,
        *,
        last_checkpoint_at: float | None = None,
        event: str | None = None,
        milestone: bool = False,
        final: bool = False,
        now: float | None = None,
    ) -> CheckpointScheduleDecision:
        now = time.time() if now is None else now
        interval = policy.checkpoint_interval_minutes
        next_due_at: float | None = None
        if last_checkpoint_at is not None and interval is not None:
            next_due_at = last_checkpoint_at + interval * 60

        if final:
            return CheckpointScheduleDecision(
                workflow_id,
                True,
                CheckpointKind.FINAL,
                "final checkpoint requested",
                last_checkpoint_at,
                next_due_at,
                event,
                milestone,
                final,
            )
        if event in RISK_EVENTS:
            return CheckpointScheduleDecision(
                workflow_id,
                True,
                CheckpointKind.EVENT_BASED,
                f"risk event detected: {event}",
                last_checkpoint_at,
                next_due_at,
                event,
                milestone,
                final,
            )
        if milestone:
            return CheckpointScheduleDecision(
                workflow_id,
                True,
                CheckpointKind.MILESTONE,
                "milestone checkpoint requested",
                last_checkpoint_at,
                next_due_at,
                event,
                milestone,
                final,
            )
        if interval is None:
            return CheckpointScheduleDecision(
                workflow_id,
                False,
                None,
                "policy has no periodic checkpoint interval",
                last_checkpoint_at,
                next_due_at,
                event,
                milestone,
                final,
            )
        if last_checkpoint_at is None:
            kind = CheckpointKind.HOURLY if profile.duration == TaskDuration.LONG else CheckpointKind.MILESTONE
            return CheckpointScheduleDecision(
                workflow_id,
                True,
                kind,
                "first scheduled checkpoint is due",
                last_checkpoint_at,
                now + interval * 60,
                event,
                milestone,
                final,
            )
        if next_due_at is not None and now >= next_due_at:
            kind = CheckpointKind.HOURLY if interval >= 60 else CheckpointKind.MILESTONE
            return CheckpointScheduleDecision(
                workflow_id,
                True,
                kind,
                "checkpoint interval elapsed",
                last_checkpoint_at,
                next_due_at,
                event,
                milestone,
                final,
            )
        return CheckpointScheduleDecision(
            workflow_id,
            False,
            None,
            "checkpoint interval has not elapsed",
            last_checkpoint_at,
            next_due_at,
            event,
            milestone,
            final,
        )
