import pytest

from processual_api.cgt_governor.policy.fanout_planner import plan_fanout_execution


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
