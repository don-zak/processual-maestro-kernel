from __future__ import annotations

from benchmarks.execution_mix_app import app, mode_for_call
from benchmarks.execution_mix_probe import percentile


def test_execution_mix_modes_are_deterministic() -> None:
    first = [mode_for_call(7, slot) for slot in range(16)]
    second = [mode_for_call(7, slot) for slot in range(16)]

    assert first == second
    assert {"fast", "normal", "slow", "timeout", "failure"}.issubset(set(first))


def test_execution_mix_percentile_uses_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    assert percentile(values, 0.50) == 30.0
    assert percentile(values, 0.95) == 50.0


def test_execution_mix_harness_registers_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/health/live" in paths
    assert "/benchmark/execution-mix" in paths
