from __future__ import annotations

from collections import defaultdict, deque

from ..adaptive_types import DriftAlert, RiskLevel


class DriftDetector:
    """Detects declining metrics across checkpoints without mutating kernel behavior."""

    def __init__(self, window: int = 3, sensitivity: float = 0.15):
        self.window = max(2, window)
        self.sensitivity = sensitivity
        self._series: dict[tuple[str, str], deque[float]] = defaultdict(lambda: deque(maxlen=self.window))

    def observe(self, entity_id: str, entity_type: str, metric: str, value: float) -> DriftAlert | None:
        key = (entity_id, metric)
        series = self._series[key]
        series.append(float(value))
        if len(series) < self.window:
            return None
        previous = series[0]
        current = series[-1]
        delta = current - previous
        if delta >= -self.sensitivity:
            return None
        severity = RiskLevel.HIGH if abs(delta) >= self.sensitivity * 2 else RiskLevel.MEDIUM
        return DriftAlert(
            entity_id=entity_id,
            entity_type=entity_type,
            metric=metric,
            previous_value=previous,
            current_value=current,
            severity=severity,
            reason=f"{metric} declined by {abs(delta):.3f} across {len(series)} checkpoints",
        )
