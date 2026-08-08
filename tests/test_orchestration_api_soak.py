from __future__ import annotations

from benchmarks.orchestration_api_probe import OrchestrationAPIResult
from benchmarks.orchestration_api_soak import summarize_results


def make_result(
    *,
    width: int,
    concurrency: int,
    successful_rps: float,
    p95_ms: float,
    backpressure_rate: float,
    errors: int = 0,
    requests: int = 120,
) -> OrchestrationAPIResult:
    success = requests - errors
    return OrchestrationAPIResult(
        workers=2,
        width=width,
        concurrency=concurrency,
        requests=requests,
        success=success,
        backpressure=0,
        errors=errors,
        duration_seconds=1.0,
        successful_rps=successful_rps,
        p50_ms=10.0,
        p95_ms=p95_ms,
        p99_ms=p95_ms,
        backpressure_rate=backpressure_rate,
        error_rate=errors / requests,
    )


def test_summarize_results_uses_medians_and_worst_backpressure() -> None:
    summaries = summarize_results(
        [
            make_result(
                width=12,
                concurrency=10,
                successful_rps=20.0,
                p95_ms=500.0,
                backpressure_rate=0.10,
            ),
            make_result(
                width=12,
                concurrency=10,
                successful_rps=24.0,
                p95_ms=700.0,
                backpressure_rate=0.25,
            ),
            make_result(
                width=12,
                concurrency=10,
                successful_rps=22.0,
                p95_ms=600.0,
                backpressure_rate=0.15,
            ),
        ]
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.trials == 3
    assert summary.total_requests == 360
    assert summary.median_successful_rps == 22.0
    assert summary.median_p95_ms == 600.0
    assert summary.max_backpressure_rate == 0.25
    assert summary.total_errors == 0


def test_summarize_results_accumulates_true_errors() -> None:
    summaries = summarize_results(
        [
            make_result(
                width=4,
                concurrency=20,
                successful_rps=80.0,
                p95_ms=300.0,
                backpressure_rate=0.20,
                errors=1,
            ),
            make_result(
                width=4,
                concurrency=20,
                successful_rps=78.0,
                p95_ms=320.0,
                backpressure_rate=0.25,
                errors=2,
            ),
        ]
    )

    assert summaries[0].total_errors == 3
