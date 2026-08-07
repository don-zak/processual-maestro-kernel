from __future__ import annotations

from benchmarks.fanout_probe import percentile


def test_fanout_percentile_uses_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    assert percentile(values, 0.50) == 30.0
    assert percentile(values, 0.95) == 50.0


def test_fanout_percentile_handles_empty_samples() -> None:
    assert percentile([], 0.95) == 0.0
