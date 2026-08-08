import asyncio

import pytest

from processual_api.cgt_governor.policy.fanout_planner import (
    execute_fanout_plan,
    plan_fanout_execution,
)


def test_planner_paces_broad_single_provider_fanout() -> None:
    plan = plan_fanout_execution(width=16, provider_count=1)

    assert plan.is_paced is True
    assert plan.local_parallelism == 2
    assert plan.reason == "broad_single_provider"


@pytest.mark.parametrize("width", [1, 8, 11])
def test_planner_leaves_narrow_single_provider_fanout_unshaped(width: int) -> None:
    plan = plan_fanout_execution(width=width, provider_count=1)

    assert plan.is_paced is False
    assert plan.local_parallelism is None
    assert plan.reason == "shared_governor_only"


@pytest.mark.parametrize("width", [8, 16, 32])
def test_planner_leaves_multi_provider_fanout_unshaped(width: int) -> None:
    plan = plan_fanout_execution(width=width, provider_count=2)

    assert plan.is_paced is False
    assert plan.local_parallelism is None


@pytest.mark.parametrize(
    ("width", "provider_count"),
    [(0, 1), (1, 0), (-1, 1), (1, -1)],
)
def test_planner_rejects_invalid_shapes(width: int, provider_count: int) -> None:
    with pytest.raises(ValueError):
        plan_fanout_execution(width=width, provider_count=provider_count)


@pytest.mark.asyncio
async def test_executor_enforces_planned_parallelism() -> None:
    plan = plan_fanout_execution(width=16, provider_count=1)
    active = 0
    peak_active = 0
    lock = asyncio.Lock()

    async def worker(item: int) -> int:
        nonlocal active, peak_active
        async with lock:
            active += 1
            peak_active = max(peak_active, active)
        await asyncio.sleep(0.01)
        async with lock:
            active -= 1
        return item * 2

    results = await execute_fanout_plan(list(range(16)), worker, plan)

    assert results == [item * 2 for item in range(16)]
    assert peak_active == 2


@pytest.mark.asyncio
async def test_executor_preserves_exception_slots() -> None:
    plan = plan_fanout_execution(width=3, provider_count=2)

    async def worker(item: int) -> int:
        if item == 1:
            raise RuntimeError("boom")
        return item

    results = await execute_fanout_plan([0, 1, 2], worker, plan)

    assert results[0] == 0
    assert isinstance(results[1], RuntimeError)
    assert results[2] == 2


@pytest.mark.asyncio
async def test_executor_rejects_plan_width_mismatch() -> None:
    plan = plan_fanout_execution(width=3, provider_count=1)

    async def worker(item: int) -> int:
        return item

    with pytest.raises(ValueError, match="plan width"):
        await execute_fanout_plan([1, 2], worker, plan)
