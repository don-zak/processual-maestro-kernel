from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FanoutExecutionPlan:
    width: int
    provider_count: int
    local_parallelism: int | None
    reason: str

    @property
    def is_paced(self) -> bool:
        return self.local_parallelism is not None


def plan_fanout_execution(*, width: int, provider_count: int) -> FanoutExecutionPlan:
    """Choose conservative request-local pacing for pathological fan-out shapes.

    The shared execution fan-out governor remains authoritative. This planner only
    limits how aggressively one orchestration request presents work to that
    governor. Empirical benchmark data showed that broad single-provider fan-out
    can otherwise collapse into near-total backpressure while multi-provider and
    narrower shapes generally perform better without request-local pacing.
    """
    if width < 1:
        raise ValueError("width must be at least 1")
    if provider_count < 1:
        raise ValueError("provider_count must be at least 1")

    if provider_count == 1 and width >= 12:
        return FanoutExecutionPlan(
            width=width,
            provider_count=provider_count,
            local_parallelism=2,
            reason="broad_single_provider",
        )

    return FanoutExecutionPlan(
        width=width,
        provider_count=provider_count,
        local_parallelism=None,
        reason="shared_governor_only",
    )
