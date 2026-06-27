from __future__ import annotations

from ..adaptive_types import AdaptiveQualityGateReport, MetricsSnapshot, RuntimeMode


class AdaptiveQualityGate:
    """Promotion/readiness gate for safe adaptive operation.

    This is a read-only guardrail. It does not change kernel behavior; it only states whether evidence is strong
    enough to move from observe/recommend operation toward controlled adaptation.
    """

    def __init__(
        self,
        min_outcome_coverage: float = 0.95,
        min_patch_success_rate: float = 0.80,
        max_false_retry_rate: float = 0.25,
        max_false_reroute_rate: float = 0.25,
        max_handoff_failure_rate: float = 0.35,
        max_agent_bloat_ratio: float = 0.35,
        min_checkpoint_accuracy: float = 0.70,
    ):
        self.min_outcome_coverage = min_outcome_coverage
        self.min_patch_success_rate = min_patch_success_rate
        self.max_false_retry_rate = max_false_retry_rate
        self.max_false_reroute_rate = max_false_reroute_rate
        self.max_handoff_failure_rate = max_handoff_failure_rate
        self.max_agent_bloat_ratio = max_agent_bloat_ratio
        self.min_checkpoint_accuracy = min_checkpoint_accuracy

    def evaluate(
        self,
        workflow_id: str,
        metrics: MetricsSnapshot,
        runtime_mode: RuntimeMode,
        pending_outcome_count: int = 0,
        pending_approval_count: int = 0,
        critical: bool = False,
    ) -> AdaptiveQualityGateReport:
        violations: list[str] = []
        warnings: list[str] = []

        if metrics.outcome_coverage_ratio < self.min_outcome_coverage:
            violations.append(
                f"outcome coverage {metrics.outcome_coverage_ratio:.2f} below {self.min_outcome_coverage:.2f}"
            )
        if pending_outcome_count:
            warnings.append(f"{pending_outcome_count} important decisions still need outcomes")
        if pending_approval_count:
            violations.append(f"{pending_approval_count} human approval requests are still pending")
        if metrics.policy_patch_success_rate < self.min_patch_success_rate:
            violations.append(
                f"policy patch success rate {metrics.policy_patch_success_rate:.2f} "
                f"below {self.min_patch_success_rate:.2f}"
            )
        if metrics.false_retry_rate > self.max_false_retry_rate:
            violations.append(f"false retry rate {metrics.false_retry_rate:.2f} is too high")
        if metrics.false_reroute_rate > self.max_false_reroute_rate:
            violations.append(f"false reroute rate {metrics.false_reroute_rate:.2f} is too high")
        if metrics.handoff_failure_rate > self.max_handoff_failure_rate:
            violations.append(f"handoff failure rate {metrics.handoff_failure_rate:.2f} is too high")
        if metrics.agent_bloat_ratio > self.max_agent_bloat_ratio:
            violations.append(f"agent bloat ratio {metrics.agent_bloat_ratio:.2f} is too high")
        if metrics.checkpoint_detection_accuracy < self.min_checkpoint_accuracy:
            violations.append(
                f"checkpoint detection accuracy {metrics.checkpoint_detection_accuracy:.2f} "
                f"below {self.min_checkpoint_accuracy:.2f}"
            )
        if critical:
            violations.append("critical workflows cannot be promoted to automatic adaptive mode")

        passed = not violations
        eligible_next_mode: RuntimeMode | None = None
        if passed:
            if runtime_mode == RuntimeMode.OBSERVE:
                eligible_next_mode = RuntimeMode.RECOMMEND
            elif runtime_mode == RuntimeMode.RECOMMEND:
                eligible_next_mode = RuntimeMode.CONTROLLED_ADAPTIVE
            elif runtime_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
                eligible_next_mode = RuntimeMode.CONTROLLED_ADAPTIVE

        return AdaptiveQualityGateReport(
            workflow_id=workflow_id,
            runtime_mode=runtime_mode,
            passed=passed,
            violations=tuple(violations),
            warnings=tuple(warnings),
            eligible_next_mode=eligible_next_mode,
            metrics=metrics,
            pending_outcome_count=pending_outcome_count,
            pending_approval_count=pending_approval_count,
        )
