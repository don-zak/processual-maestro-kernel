from __future__ import annotations

import httpx
import pytest

from benchmarks.workload_probe import (
    Result,
    capacity_usage,
    first_backpressure,
    first_saturation,
    percentile,
    weighted_rates,
)


def _result(
    *,
    concurrency: int,
    rps: float = 100.0,
    p95_ms: float = 20.0,
    backpressure: int = 0,
    errors: int = 0,
) -> Result:
    requests = 100
    return Result(
        workload="test",
        concurrency=concurrency,
        requests=requests,
        success=requests - backpressure - errors,
        backpressure=backpressure,
        errors=errors,
        backpressure_rate=backpressure / requests,
        error_rate=errors / requests,
        duration_seconds=1.0,
        throughput_rps=rps,
        admitted_ocu_total=200.0,
        ocu_seconds_total=8.0,
        admitted_ocu_per_second=200.0,
        average_active_ocu=8.0,
        p50_ms=10.0,
        p95_ms=p95_ms,
        p99_ms=p95_ms,
        max_ms=p95_ms,
    )


def test_percentile_uses_nearest_rank() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    assert percentile(values, 0.50) == 3.0
    assert percentile(values, 0.95) == 5.0
    assert percentile([], 0.95) == 0.0


def test_capacity_usage_reads_only_non_negative_capacity_headers() -> None:
    response = httpx.Response(
        200,
        headers={
            "X-Maestro-Capacity-OCU": "4",
            "X-Maestro-Capacity-OCU-Seconds": "0.75",
        },
    )

    assert capacity_usage(response) == pytest.approx((4.0, 0.75))

    malformed = httpx.Response(
        200,
        headers={
            "X-Maestro-Capacity-OCU": "not-a-number",
            "X-Maestro-Capacity-OCU-Seconds": "-3",
        },
    )
    assert capacity_usage(malformed) == (0.0, 0.0)


def test_weighted_rates_separate_admission_rate_from_occupancy() -> None:
    admitted_rate, average_active = weighted_rates(
        admitted_ocu_total=900.0,
        ocu_seconds_total=72.0,
        elapsed_seconds=9.0,
    )

    assert admitted_rate == pytest.approx(100.0)
    assert average_active == pytest.approx(8.0)
    assert weighted_rates(
        admitted_ocu_total=10.0,
        ocu_seconds_total=4.0,
        elapsed_seconds=0.0,
    ) == (0.0, 0.0)


def test_first_backpressure_is_not_counted_as_true_error() -> None:
    results = [
        _result(concurrency=1),
        _result(concurrency=10),
        _result(concurrency=20, backpressure=5),
        _result(concurrency=40, backpressure=15),
    ]

    assert first_backpressure(results) == 20
    assert first_saturation(results) is None


def test_saturation_detects_latency_regression_before_failures() -> None:
    results = [
        _result(concurrency=1, rps=100.0, p95_ms=20.0),
        _result(concurrency=10, rps=250.0, p95_ms=70.0),
        _result(concurrency=20, rps=270.0, p95_ms=150.0),
        _result(concurrency=40, rps=275.0, p95_ms=310.0),
    ]

    assert first_saturation(results) == 40


def test_saturation_detects_throughput_collapse() -> None:
    results = [
        _result(concurrency=1, rps=100.0, p95_ms=20.0),
        _result(concurrency=10, rps=300.0, p95_ms=80.0),
        _result(concurrency=20, rps=190.0, p95_ms=100.0),
    ]

    assert first_saturation(results) == 20
