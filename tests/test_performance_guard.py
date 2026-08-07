from __future__ import annotations

from copy import deepcopy

from benchmarks.performance_guard import evaluate


def _stage(
    concurrency: int,
    *,
    p95_ms: float,
    admitted_ocu_per_second: float,
    backpressure_rate: float = 0.0,
    error_rate: float = 0.0,
) -> dict[str, object]:
    return {
        "concurrency": concurrency,
        "p95_ms": p95_ms,
        "admitted_ocu_per_second": admitted_ocu_per_second,
        "backpressure_rate": backpressure_rate,
        "error_rate": error_rate,
    }


def _healthy_payload() -> dict[str, object]:
    return {
        "light": {
            "saturation_concurrency": None,
            "results": [
                _stage(40, p95_ms=200.0, admitted_ocu_per_second=0.0),
            ],
        },
        "normal": {
            "saturation_concurrency": 20,
            "results": [
                _stage(
                    20,
                    p95_ms=320.0,
                    admitted_ocu_per_second=400.0,
                    backpressure_rate=0.10,
                ),
                _stage(
                    40,
                    p95_ms=430.0,
                    admitted_ocu_per_second=350.0,
                    backpressure_rate=0.20,
                ),
            ],
        },
        "heavy": {
            "saturation_concurrency": 40,
            "results": [
                _stage(20, p95_ms=250.0, admitted_ocu_per_second=500.0),
                _stage(40, p95_ms=500.0, admitted_ocu_per_second=400.0),
            ],
        },
        "governance-heavy": {
            "saturation_concurrency": 20,
            "results": [
                _stage(20, p95_ms=350.0, admitted_ocu_per_second=400.0),
                _stage(40, p95_ms=450.0, admitted_ocu_per_second=350.0),
            ],
        },
    }


def test_healthy_benchmark_passes_regression_guard() -> None:
    assert evaluate(_healthy_payload()) == []


def test_guard_detects_latency_and_true_error_regressions() -> None:
    payload = deepcopy(_healthy_payload())
    normal = payload["normal"]
    assert isinstance(normal, dict)
    results = normal["results"]
    assert isinstance(results, list)
    stage = results[0]
    assert isinstance(stage, dict)
    stage["p95_ms"] = 900.0
    stage["error_rate"] = 0.02

    violations = evaluate(payload)

    assert any("normal@20: p95" in violation for violation in violations)
    assert any("normal@20: true error rate" in violation for violation in violations)


def test_guard_detects_weighted_throughput_collapse() -> None:
    payload = deepcopy(_healthy_payload())
    heavy = payload["heavy"]
    assert isinstance(heavy, dict)
    results = heavy["results"]
    assert isinstance(results, list)
    stage = results[0]
    assert isinstance(stage, dict)
    stage["admitted_ocu_per_second"] = 100.0

    violations = evaluate(payload)

    assert any("heavy@20: admitted OCU/s" in violation for violation in violations)


def test_guard_detects_excessive_backpressure() -> None:
    payload = deepcopy(_healthy_payload())
    normal = payload["normal"]
    assert isinstance(normal, dict)
    results = normal["results"]
    assert isinstance(results, list)
    stage = results[1]
    assert isinstance(stage, dict)
    stage["backpressure_rate"] = 0.50

    violations = evaluate(payload)

    assert any("normal@40: backpressure" in violation for violation in violations)


def test_guard_detects_early_saturation() -> None:
    payload = deepcopy(_healthy_payload())
    governance = payload["governance-heavy"]
    assert isinstance(governance, dict)
    governance["saturation_concurrency"] = 10

    violations = evaluate(payload)

    assert any("governance-heavy: saturation starts at 10" in item for item in violations)
