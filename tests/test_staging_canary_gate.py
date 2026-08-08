from benchmarks.staging_canary_gate import evaluate_canary_gate


def workload_payload(*, p95: float, ocu: float, bp: float = 0.0, errors: float = 0.0):
    return {
        workload: {
            "results": [
                {
                    "concurrency": 40,
                    "p95_ms": p95,
                    "admitted_ocu_per_second": ocu,
                    "backpressure_rate": bp,
                    "error_rate": errors,
                }
            ]
        }
        for workload in ("normal", "heavy", "governance-heavy")
    }


def execution_mix_payload(success_rps: float, *, bp: float = 0.0, errors: float = 0.0):
    return [
        {
            "providers": 2,
            "width": width,
            "concurrency": 40,
            "p95_ms": 100.0,
            "successful_rps": success_rps,
            "backpressure_rate": bp,
            "error_rate": errors,
        }
        for width in (4, 8)
    ]


def test_two_worker_canary_gate_passes_on_clear_capacity_gain() -> None:
    result = evaluate_canary_gate(
        workload_payload(p95=100.0, ocu=100.0),
        workload_payload(p95=95.0, ocu=120.0),
        execution_mix_payload(10.0),
        execution_mix_payload(12.0),
    )

    assert result.passed is True
    assert result.violations == ()


def test_two_worker_canary_gate_allows_small_local_ocu_tradeoff() -> None:
    one_worker = workload_payload(p95=100.0, ocu=100.0)
    two_workers = workload_payload(p95=95.0, ocu=120.0)
    two_workers["heavy"]["results"][0]["admitted_ocu_per_second"] = 95.0

    result = evaluate_canary_gate(
        one_worker,
        two_workers,
        execution_mix_payload(10.0),
        execution_mix_payload(12.0),
    )

    assert result.passed is True


def test_two_worker_canary_gate_rejects_weak_or_regressive_candidate() -> None:
    result = evaluate_canary_gate(
        workload_payload(p95=100.0, ocu=100.0, bp=0.10),
        workload_payload(p95=120.0, ocu=80.0, bp=0.20),
        execution_mix_payload(10.0, bp=0.10),
        execution_mix_payload(9.0, bp=0.20),
    )

    assert result.passed is False
    assert any("aggregate OCU/s gain" in item for item in result.violations)
    assert any("OCU/s regression" in item for item in result.violations)
    assert any("p95 regression" in item for item in result.violations)
    assert any("successful RPS gain" in item for item in result.violations)
    assert any("backpressure regression" in item for item in result.violations)
