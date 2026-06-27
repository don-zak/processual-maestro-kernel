from __future__ import annotations

from collections import deque

from ..adaptive_types import AdaptiveConvergenceReport, AdaptiveCycleReport


class AdaptiveConvergenceMonitor:
    """Tracks whether adaptive cycles are stabilizing before deeper runtime expansion."""

    def __init__(
        self, window_size: int = 5, min_outcome_coverage: float = 0.90, min_checkpoint_confidence: float = 0.65
    ):
        self.window_size = max(2, window_size)
        self.min_outcome_coverage = min_outcome_coverage
        self.min_checkpoint_confidence = min_checkpoint_confidence
        self._windows: dict[str, deque[AdaptiveCycleReport]] = {}

    def observe(self, report: AdaptiveCycleReport) -> AdaptiveConvergenceReport:
        window = self._windows.setdefault(report.workflow_id, deque(maxlen=self.window_size))
        window.append(report)
        return self.evaluate(report.workflow_id)

    def evaluate(self, workflow_id: str) -> AdaptiveConvergenceReport:
        window = tuple(self._windows.get(workflow_id, ()))
        reasons: list[str] = []
        if not window:
            return AdaptiveConvergenceReport(
                workflow_id=workflow_id,
                stable=False,
                window_size=0,
                avg_outcome_coverage=0.0,
                max_violation_count=0,
                avg_checkpoint_confidence=0.0,
                recommendation="observe_more",
                reasons=("no adaptive cycles have been recorded",),
            )
        avg_coverage = sum(r.outcome_coverage_ratio for r in window) / len(window)
        max_violations = max((len(r.runtime_invariants.violations) if r.runtime_invariants else 0) for r in window)
        checkpoints = [r.checkpoint.confidence for r in window if r.checkpoint is not None]
        avg_checkpoint = sum(checkpoints) / len(checkpoints) if checkpoints else 1.0
        if len(window) < self.window_size:
            reasons.append(f"only {len(window)} cycle(s) available; target window is {self.window_size}")
        if avg_coverage < self.min_outcome_coverage:
            reasons.append(f"average outcome coverage {avg_coverage:.2f} below {self.min_outcome_coverage:.2f}")
        if max_violations:
            reasons.append(f"runtime invariant violations observed: {max_violations}")
        if avg_checkpoint < self.min_checkpoint_confidence:
            reasons.append(f"checkpoint confidence {avg_checkpoint:.2f} below {self.min_checkpoint_confidence:.2f}")
        stable = len(window) >= self.window_size and not reasons
        recommendation = "eligible_for_cautious_expansion" if stable else "hold_or_demote"
        return AdaptiveConvergenceReport(
            workflow_id=workflow_id,
            stable=stable,
            window_size=len(window),
            avg_outcome_coverage=round(avg_coverage, 4),
            max_violation_count=max_violations,
            avg_checkpoint_confidence=round(avg_checkpoint, 4),
            recommendation=recommendation,
            reasons=tuple(reasons),
        )
