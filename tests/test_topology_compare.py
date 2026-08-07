from __future__ import annotations

from benchmarks.topology_compare import compare


def _payload(*, p95: float, ocu_per_second: float, backpressure: float, errors: float = 0.0):
    return {
        workload: {
            "results": [
                {
                    "concurrency": 40,
                    "p95_ms": p95,
                    "admitted_ocu_per_second": ocu_per_second,
                    "backpressure_rate": backpressure,
                    "error_rate": errors,
                }
            ]
        }
        for workload in ("normal", "heavy", "governance-heavy")
    }


def test_compare_reports_worker_scaling_delta() -> None:
    one_worker = _payload(p95=400.0, ocu_per_second=250.0, backpressure=0.20)
    two_workers = _payload(p95=320.0, ocu_per_second=325.0, backpressure=0.10)

    deltas = compare(one_worker, two_workers)

    assert len(deltas) == 3
    assert all(item.p95_change_pct == -20.0 for item in deltas)
    assert all(item.ocu_per_second_change_pct == 30.0 for item in deltas)
    assert all(item.true_error_rate_max == 0.0 for item in deltas)


def test_compare_preserves_backpressure_and_true_error_signals() -> None:
    one_worker = _payload(p95=300.0, ocu_per_second=300.0, backpressure=0.25, errors=0.0)
    two_workers = _payload(p95=310.0, ocu_per_second=305.0, backpressure=0.15, errors=0.02)

    deltas = compare(one_worker, two_workers)

    assert all(item.one_worker_backpressure_rate == 0.25 for item in deltas)
    assert all(item.two_worker_backpressure_rate == 0.15 for item in deltas)
    assert all(item.true_error_rate_max == 0.02 for item in deltas)
