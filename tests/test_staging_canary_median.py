from benchmarks.staging_canary_median import evaluate_median_canary


def workload_trial(
    *,
    normal_ocu: float,
    heavy_ocu: float,
    governance_ocu: float,
    normal_p95: float = 100.0,
    heavy_p95: float = 100.0,
    governance_p95: float = 100.0,
):
    values = {
        "normal": (normal_ocu, normal_p95),
        "heavy": (heavy_ocu, heavy_p95),
        "governance-heavy": (governance_ocu, governance_p95),
    }
    return {
        workload: {
            "results": [
                {
                    "concurrency": 40,
                    "admitted_ocu_per_second": ocu,
                    "p95_ms": p95,
                    "backpressure_rate": 0.0,
                    "error_rate": 0.0,
                }
            ]
        }
        for workload, (ocu, p95) in values.items()
    }


def execution_trial(successful_rps: float):
    return [
        {
            "workers": 1,
            "providers": 2,
            "width": width,
            "concurrency": 40,
            "successful_rps": successful_rps,
            "p95_ms": 100.0,
            "backpressure_rate": 0.0,
            "error_rate": 0.0,
        }
        for width in (4, 8)
    ]


def test_median_canary_ignores_one_bad_outlier() -> None:
    one_worker = [
        workload_trial(normal_ocu=100.0, heavy_ocu=100.0, governance_ocu=100.0)
        for _ in range(3)
    ]
    two_workers = [
        workload_trial(normal_ocu=130.0, heavy_ocu=105.0, governance_ocu=125.0),
        workload_trial(normal_ocu=128.0, heavy_ocu=104.0, governance_ocu=123.0),
        workload_trial(
            normal_ocu=70.0,
            heavy_ocu=60.0,
            governance_ocu=65.0,
            normal_p95=150.0,
            heavy_p95=180.0,
            governance_p95=160.0,
        ),
    ]

    result = evaluate_median_canary(
        one_worker,
        two_workers,
        [execution_trial(10.0) for _ in range(3)],
        [execution_trial(value) for value in (14.0, 13.5, 4.0)],
    )

    assert result.passed is True
    assert result.violations == ()


def test_median_canary_rejects_repeatable_heavy_regression() -> None:
    one_worker = [
        workload_trial(normal_ocu=100.0, heavy_ocu=100.0, governance_ocu=100.0)
        for _ in range(3)
    ]
    two_workers = [
        workload_trial(
            normal_ocu=130.0,
            heavy_ocu=80.0,
            governance_ocu=125.0,
            heavy_p95=125.0,
        ),
        workload_trial(
            normal_ocu=128.0,
            heavy_ocu=82.0,
            governance_ocu=123.0,
            heavy_p95=122.0,
        ),
        workload_trial(
            normal_ocu=132.0,
            heavy_ocu=85.0,
            governance_ocu=126.0,
            heavy_p95=120.0,
        ),
    ]

    result = evaluate_median_canary(
        one_worker,
        two_workers,
        [execution_trial(10.0) for _ in range(3)],
        [execution_trial(14.0) for _ in range(3)],
    )

    assert result.passed is False
    assert any("heavy@c40: OCU/s regression" in item for item in result.violations)
    assert any("heavy@c40: p95 regression" in item for item in result.violations)
