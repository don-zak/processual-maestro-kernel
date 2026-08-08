import math

import pytest

from processual_api.execution.adaptive import (
    AdaptiveConcurrencyController,
    AdaptiveConcurrencyPolicy,
    AdaptiveConcurrencySample,
)


def controller(*, initial_limit: int = 4) -> AdaptiveConcurrencyController:
    return AdaptiveConcurrencyController(
        AdaptiveConcurrencyPolicy(
            minimum=1,
            maximum=8,
            additive_step=1,
            decrease_ratio=0.5,
            latency_target_ms=100.0,
            error_rate_threshold=0.1,
            recovery_windows=3,
            pressure_windows=2,
            healthy_latency_ratio=0.9,
            ewma_alpha=1.0,
        ),
        initial_limit=initial_limit,
    )


def healthy() -> AdaptiveConcurrencySample:
    return AdaptiveConcurrencySample(requests=100, latency_p95_ms=60.0)


def test_healthy_windows_increase_gradually() -> None:
    adaptive = controller(initial_limit=4)

    assert adaptive.observe(healthy()) == 4
    assert adaptive.observe(healthy()) == 4
    assert adaptive.observe(healthy()) == 5
    assert adaptive.observe(healthy()) == 5


def test_rate_limit_reduces_immediately() -> None:
    adaptive = controller(initial_limit=8)

    limit = adaptive.observe(
        AdaptiveConcurrencySample(
            requests=100,
            latency_p95_ms=70.0,
            rate_limited=1,
        )
    )

    assert limit == 4


def test_timeout_reduces_immediately() -> None:
    adaptive = controller(initial_limit=6)

    limit = adaptive.observe(
        AdaptiveConcurrencySample(
            requests=100,
            latency_p95_ms=70.0,
            timeouts=1,
        )
    )

    assert limit == 3


def test_soft_pressure_requires_hysteresis() -> None:
    adaptive = controller(initial_limit=8)
    pressure = AdaptiveConcurrencySample(requests=100, latency_p95_ms=150.0)

    assert adaptive.observe(pressure) == 8
    assert adaptive.observe(pressure) == 4


def test_error_pressure_requires_hysteresis() -> None:
    adaptive = controller(initial_limit=8)
    pressure = AdaptiveConcurrencySample(requests=100, latency_p95_ms=70.0, errors=10)

    assert adaptive.observe(pressure) == 8
    assert adaptive.observe(pressure) == 4


def test_floor_and_ceiling_are_enforced() -> None:
    low = controller(initial_limit=1)
    high = controller(initial_limit=8)

    assert low.observe(
        AdaptiveConcurrencySample(requests=10, latency_p95_ms=50.0, timeouts=1)
    ) == 1
    for _ in range(6):
        high.observe(healthy())
    assert high.current_limit == 8


def test_recovery_after_pressure_is_gradual() -> None:
    adaptive = controller(initial_limit=8)
    adaptive.observe(AdaptiveConcurrencySample(requests=10, latency_p95_ms=60.0, rate_limited=1))
    assert adaptive.current_limit == 4

    assert adaptive.observe(healthy()) == 4
    assert adaptive.observe(healthy()) == 4
    assert adaptive.observe(healthy()) == 5


@pytest.mark.parametrize(
    "sample",
    [
        AdaptiveConcurrencySample(requests=0, latency_p95_ms=10.0),
        AdaptiveConcurrencySample(requests=-1, latency_p95_ms=10.0),
        AdaptiveConcurrencySample(requests=10, latency_p95_ms=-1.0),
        AdaptiveConcurrencySample(requests=10, latency_p95_ms=math.nan),
        AdaptiveConcurrencySample(requests=10, latency_p95_ms=10.0, errors=11),
        AdaptiveConcurrencySample(requests=10, latency_p95_ms=10.0, timeouts=11),
    ],
)
def test_invalid_samples_are_safe_noops(sample: AdaptiveConcurrencySample) -> None:
    adaptive = controller(initial_limit=4)

    assert adaptive.observe(sample) == 4
    assert adaptive.latency_ewma_ms is None


def test_intermittent_pressure_does_not_oscillate_limit() -> None:
    adaptive = controller(initial_limit=6)
    pressure = AdaptiveConcurrencySample(requests=100, latency_p95_ms=140.0)

    assert adaptive.observe(pressure) == 6
    assert adaptive.observe(healthy()) == 6
    assert adaptive.observe(pressure) == 6
    assert adaptive.observe(healthy()) == 6
    assert adaptive.current_limit == 6
