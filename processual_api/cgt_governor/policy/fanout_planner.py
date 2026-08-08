from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar


ItemT = TypeVar("ItemT")
ResultT = TypeVar("ResultT")


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


async def execute_fanout_plan(
    items: Sequence[ItemT],
    worker: Callable[[ItemT], Awaitable[ResultT]],
    plan: FanoutExecutionPlan,
) -> list[ResultT | BaseException]:
    """Execute one orchestration fan-out according to a previously chosen plan.

    Exceptions are returned in their original slot, matching ``asyncio.gather``
    with ``return_exceptions=True``. The shared execution governor therefore
    remains responsible for authoritative saturation and failure semantics.
    """
    if len(items) != plan.width:
        raise ValueError("fanout plan width must match item count")

    semaphore = (
        asyncio.Semaphore(plan.local_parallelism)
        if plan.local_parallelism is not None
        else None
    )

    async def one(item: ItemT) -> ResultT:
        if semaphore is None:
            return await worker(item)
        async with semaphore:
            return await worker(item)

    return list(
        await asyncio.gather(
            *(one(item) for item in items),
            return_exceptions=True,
        )
    )
