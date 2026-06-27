from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..adaptive_types import (
    AdaptiveCycleReport,
    CheckpointReport,
    DecisionOutcome,
    PolicyProfile,
    WorkflowHistoryEvent,
)
from ..types import MaestroAction


class WorkflowHistoryRecorder:
    """Records workflow history events for offline replay and final adaptive review.

    This recorder is intentionally outside the core kernel. It derives a replayable timeline from adaptive
    checkpoints, decisions, outcomes, and cycle reports without mutating Ψ equations or cgtlib behavior.
    """

    def __init__(self):
        self._events: dict[str, list[WorkflowHistoryEvent]] = defaultdict(list)

    def record(self, event: WorkflowHistoryEvent) -> WorkflowHistoryEvent:
        self._events[event.workflow_id].append(event)
        return event

    def record_checkpoint(self, report: CheckpointReport) -> tuple[WorkflowHistoryEvent, ...]:
        events: list[WorkflowHistoryEvent] = []
        base_metadata = {
            "checkpoint_number": report.checkpoint_number,
            "checkpoint_kind": report.kind.value,
            "confidence": report.confidence,
            "risks": list(report.risks),
        }
        events.append(
            self.record(
                WorkflowHistoryEvent(
                    workflow_id=report.workflow_id,
                    event_type="checkpoint",
                    action=report.recommended_action,
                    policy_name=report.policy_name,
                    quality_delta=0.02 if report.confidence >= 0.75 else -0.01,
                    latency_delta=-0.01
                    if report.recommended_action in {MaestroAction.REROUTE, MaestroAction.PAUSE}
                    else 0.0,
                    metadata=base_metadata,
                    created_at=report.created_at,
                )
            )
        )
        for risk in report.risks:
            if risk.startswith("weak_handoffs"):
                events.append(
                    self.record(
                        WorkflowHistoryEvent(
                            workflow_id=report.workflow_id,
                            event_type="handoff_degradation",
                            action=MaestroAction.REROUTE,
                            policy_name=report.policy_name,
                            quality_delta=0.03,
                            latency_delta=-0.01,
                            metadata={**base_metadata, "risk": risk},
                            created_at=report.created_at,
                        )
                    )
                )
            elif risk.startswith("failed_steps"):
                events.append(
                    self.record(
                        WorkflowHistoryEvent(
                            workflow_id=report.workflow_id,
                            event_type="repeated_failure",
                            action=MaestroAction.RETRY,
                            policy_name=report.policy_name,
                            quality_delta=-0.01,
                            cost_delta=0.03,
                            latency_delta=0.03,
                            metadata={**base_metadata, "risk": risk},
                            created_at=report.created_at,
                        )
                    )
                )
        return tuple(events)

    def record_outcome(
        self, workflow_id: str, outcome: DecisionOutcome, policy: PolicyProfile | None = None
    ) -> WorkflowHistoryEvent:
        action = None
        try:
            action = MaestroAction(outcome.action)
        except ValueError:
            action = None
        return self.record(
            WorkflowHistoryEvent(
                workflow_id=workflow_id,
                event_type="decision_outcome",
                action=action,
                policy_name=policy.name if policy is not None else None,
                quality_delta=outcome.quality_delta,
                cost_delta=outcome.cost_delta,
                latency_delta=outcome.latency_delta,
                success_probability_delta=outcome.success_probability_delta,
                metadata={
                    "decision_id": outcome.decision_id,
                    "actual_result": outcome.actual_result,
                    "decision_quality": outcome.decision_quality,
                },
                created_at=outcome.created_at,
            )
        )

    def record_cycle(self, report: AdaptiveCycleReport) -> WorkflowHistoryEvent:
        return self.record(
            WorkflowHistoryEvent(
                workflow_id=report.workflow_id,
                event_type="adaptive_cycle",
                action=report.budget_action
                or (report.strategy_suggestion.strategy if report.strategy_suggestion else None),
                policy_name=report.policy.name,
                quality_delta=0.01 if report.checkpoint is not None else 0.0,
                metadata={
                    "decision_id": report.decision_id,
                    "checkpoint_created": report.checkpoint is not None,
                    "drift_alert_count": len(report.drift_alerts),
                    "handoff_suggestion_count": len(report.handoff_suggestions),
                    "patch_count": len(report.policy_patches),
                    "outcome_coverage_ratio": report.outcome_coverage_ratio,
                },
                created_at=report.created_at,
            )
        )

    def extend(self, workflow_id: str, events: Iterable[WorkflowHistoryEvent]) -> None:
        self._events[workflow_id].extend(events)

    def history(self, workflow_id: str) -> tuple[WorkflowHistoryEvent, ...]:
        return tuple(self._events.get(workflow_id, ()))

    def clear(self, workflow_id: str | None = None) -> None:
        if workflow_id is None:
            self._events.clear()
        else:
            self._events.pop(workflow_id, None)
