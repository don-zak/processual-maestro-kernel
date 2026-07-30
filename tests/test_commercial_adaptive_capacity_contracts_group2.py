import pytest

from processual_api.billing.commercial_adaptive_capacity_contracts import (
    ADAPTIVE_CAPACITY_ENABLED,
    ADAPTIVE_CAPACITY_MODE,
    EMERGENCY_LOAD_SHEDDING_ENABLED,
    HARD_LIMIT_ENFORCEMENT_ENABLED,
    SOFT_LIMIT_ENFORCEMENT_ENABLED,
    CapacitySnapshot,
    PlatformLoadState,
    adaptive_capacity_review_payload,
    classify_platform_load,
    decide_adaptive_capacity,
    effective_concurrency_limit,
)


def snapshot(
    *,
    running_jobs: int = 0,
    units_per_hour: int = 0,
    utilization: float = 0.0,
) -> CapacitySnapshot:
    return CapacitySnapshot(
        running_jobs=running_jobs,
        reserved_jobs=0,
        queued_jobs=0,
        units_per_hour=units_per_hour,
        worker_utilization=utilization,
        cpu_utilization=utilization,
        memory_utilization=utilization,
        database_pool_utilization=utilization,
        database_latency_p95_ratio=utilization,
        queue_wait_p95_ratio=utilization,
        task_latency_p95_ratio=utilization,
        task_latency_p99_ratio=utilization,
        error_rate_ratio=0.0,
        retry_rate_ratio=0.0,
    )


def test_adaptive_capacity_is_observe_only() -> None:
    payload = adaptive_capacity_review_payload()

    assert ADAPTIVE_CAPACITY_ENABLED is False
    assert ADAPTIVE_CAPACITY_MODE == "observe_only"
    assert SOFT_LIMIT_ENFORCEMENT_ENABLED is False
    assert HARD_LIMIT_ENFORCEMENT_ENABLED is False
    assert EMERGENCY_LOAD_SHEDDING_ENABLED is False
    assert payload["enabled"] is False


@pytest.mark.parametrize(
    ("utilization", "expected"),
    [
        (0.20, PlatformLoadState.OPEN),
        (0.50, PlatformLoadState.NORMAL),
        (0.70, PlatformLoadState.CONSTRAINED),
        (0.85, PlatformLoadState.PROTECTIVE),
        (0.95, PlatformLoadState.EMERGENCY),
    ],
)
def test_platform_load_state_is_progressive(
    utilization: float,
    expected: PlatformLoadState,
) -> None:
    assert (
        classify_platform_load(snapshot(utilization=utilization))
        is expected
    )


def test_emergency_running_job_limit_is_recognized() -> None:
    assert (
        classify_platform_load(snapshot(running_jobs=120))
        is PlatformLoadState.EMERGENCY
    )


def test_emergency_hourly_unit_limit_is_recognized() -> None:
    assert (
        classify_platform_load(snapshot(units_per_hour=600_000))
        is PlatformLoadState.EMERGENCY
    )


def test_open_state_exposes_maximum_elastic_headroom() -> None:
    assert (
        effective_concurrency_limit(
            guaranteed_concurrency=2,
            maximum_elastic_concurrency=10,
            state=PlatformLoadState.OPEN,
        )
        == 10
    )


def test_protective_state_returns_to_guaranteed_concurrency() -> None:
    assert (
        effective_concurrency_limit(
            guaranteed_concurrency=2,
            maximum_elastic_concurrency=10,
            state=PlatformLoadState.PROTECTIVE,
        )
        == 2
    )


def test_observe_only_decision_does_not_enforce_rejection() -> None:
    decision = decide_adaptive_capacity(
        snapshot(utilization=0.85)
    )

    assert decision.state is PlatformLoadState.PROTECTIVE
    assert decision.queue_new_work is True
    assert decision.enforcement_enabled is False


def test_negative_capacity_values_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="capacity counters must not be negative",
    ):
        snapshot(running_jobs=-1)
