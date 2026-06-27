from __future__ import annotations

from ..adaptive_types import ExecutionTempo, PolicyProfile, RiskLevel, TaskDuration, TaskProfile, TaskSize, TempoPlan


class TempoController:
    """Chooses execution rhythm based on task profile and selected policy."""

    def plan(self, profile: TaskProfile, policy: PolicyProfile) -> TempoPlan:
        if profile.risk == RiskLevel.CRITICAL:
            tempo = ExecutionTempo.INTENSIVE
            budget_threshold = 0.80
        elif profile.risk == RiskLevel.HIGH:
            tempo = ExecutionTempo.CAUTIOUS
            budget_threshold = 0.85
        elif profile.duration == TaskDuration.LONG or profile.size == TaskSize.LARGE:
            tempo = ExecutionTempo.BALANCED
            budget_threshold = 0.90
        elif profile.size == TaskSize.SMALL and profile.duration == TaskDuration.SHORT:
            tempo = ExecutionTempo.FAST
            budget_threshold = 0.95
        else:
            tempo = ExecutionTempo.BALANCED
            budget_threshold = 0.90

        return TempoPlan(
            tempo=tempo,
            max_agents=policy.max_agents,
            max_retries=policy.max_retries,
            allow_parallel_execution=policy.parallel_execution and tempo != ExecutionTempo.CAUTIOUS,
            checkpoint_interval_minutes=policy.checkpoint_interval_minutes,
            monitor_drift=tempo in (ExecutionTempo.BALANCED, ExecutionTempo.CAUTIOUS, ExecutionTempo.INTENSIVE),
            budget_stop_threshold=budget_threshold,
            notes=("tempo derived from profile",),
        )
