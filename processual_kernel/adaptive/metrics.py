from __future__ import annotations

from collections.abc import Iterable

from ..adaptive_types import CheckpointReport, DecisionOutcome, MetricsSnapshot, PolicyPatch
from ..types import AgentState, MaestroAction, WorkflowState
from .ledger import DecisionLedger


class AdaptiveMetricsCollector:
    """Aggregates the success metrics named by the technical paper.

    The collector is deliberately read-only. It summarizes kernel state, checkpoint confidence, decision outcomes,
    and patch history without changing the core kernel or adaptive policies.
    """

    def snapshot(
        self,
        kernel,
        outcomes: Iterable[DecisionOutcome] = (),
        checkpoints: Iterable[CheckpointReport] = (),
        ledger: DecisionLedger | None = None,
        applied_patches: Iterable[PolicyPatch] = (),
        successful_patch_versions: Iterable[str] = (),
    ) -> MetricsSnapshot:
        workflows = list(kernel.workflows.values()) if hasattr(kernel, "workflows") else []
        handoffs = list(kernel.handoffs.values()) if hasattr(kernel, "handoffs") else []
        agents = list(kernel.registry.values()) if hasattr(kernel, "registry") else []
        outcome_list = list(outcomes)
        checkpoint_list = list(checkpoints)
        patch_list = list(applied_patches)
        successful_versions = set(successful_patch_versions)

        completed = sum(1 for w in workflows if w.state == WorkflowState.COMPLETED)
        workflow_success_rate = completed / len(workflows) if workflows else 0.0

        failed_handoffs = sum(1 for h in handoffs if h.state != AgentState.ACTIVE or h.psi < 0.0)
        handoff_failure_rate = failed_handoffs / len(handoffs) if handoffs else 0.0

        successful_workflows = max(1, completed)
        cost_pressure_sum = sum(float(getattr(w.last_coefficients, "M", 0.0) or 0.0) for w in workflows)
        cost_per_successful_workflow = cost_pressure_sum / successful_workflows if workflows else 0.0

        retry_outcomes = [o for o in outcome_list if o.action == MaestroAction.RETRY.value or o.action == "retry"]
        reroute_outcomes = [o for o in outcome_list if o.action == MaestroAction.REROUTE.value or o.action == "reroute"]
        escalation_outcomes = [
            o for o in outcome_list if o.action == MaestroAction.ESCALATE.value or o.action == "escalate"
        ]

        false_retry_rate = self._low_quality_rate(retry_outcomes)
        false_reroute_rate = self._low_quality_rate(reroute_outcomes)
        late_escalation_rate = (
            sum(1 for o in escalation_outcomes if o.actual_result.lower() in {"late", "failed", "too_late"})
            / len(escalation_outcomes)
            if escalation_outcomes
            else 0.0
        )
        unnecessary_escalation_rate = (
            sum(1 for o in escalation_outcomes if o.actual_result.lower() in {"unnecessary", "no_change"})
            / len(escalation_outcomes)
            if escalation_outcomes
            else 0.0
        )

        recovery_values = [-o.recovery_time_delta for o in outcome_list if o.recovery_time_delta != 0.0]
        recovery_time = sum(recovery_values) / len(recovery_values) if recovery_values else 0.0

        bloated = sum(1 for a in agents if a.state in (AgentState.ARCHIVED, AgentState.QUARANTINED))
        agent_bloat_ratio = bloated / len(agents) if agents else 0.0

        checkpoint_detection_accuracy = (
            sum(r.confidence for r in checkpoint_list) / len(checkpoint_list) if checkpoint_list else 1.0
        )

        if patch_list:
            successful = sum(1 for p in patch_list if p.policy_version_to in successful_versions or p.reason)
            policy_patch_success_rate = successful / len(patch_list)
        else:
            policy_patch_success_rate = 1.0

        outcome_coverage_ratio = ledger.coverage_ratio() if ledger is not None else 1.0

        return MetricsSnapshot(
            workflow_success_rate=round(workflow_success_rate, 4),
            handoff_failure_rate=round(handoff_failure_rate, 4),
            recovery_time=round(recovery_time, 4),
            cost_per_successful_workflow=round(cost_per_successful_workflow, 4),
            false_retry_rate=round(false_retry_rate, 4),
            false_reroute_rate=round(false_reroute_rate, 4),
            late_escalation_rate=round(late_escalation_rate, 4),
            unnecessary_escalation_rate=round(unnecessary_escalation_rate, 4),
            agent_bloat_ratio=round(agent_bloat_ratio, 4),
            checkpoint_detection_accuracy=round(checkpoint_detection_accuracy, 4),
            policy_patch_success_rate=round(policy_patch_success_rate, 4),
            outcome_coverage_ratio=round(outcome_coverage_ratio, 4),
            workflow_count=len(workflows),
            decision_outcome_count=len(outcome_list),
            checkpoint_count=len(checkpoint_list),
        )

    @staticmethod
    def _low_quality_rate(outcomes: list[DecisionOutcome]) -> float:
        if not outcomes:
            return 0.0
        return sum(1 for o in outcomes if o.decision_quality < 0.45) / len(outcomes)
