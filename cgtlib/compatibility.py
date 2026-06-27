from __future__ import annotations

from cgtlib.private import compute as _compute


def compute_compatibility(source_features: dict[str, float], target_features: dict[str, float], weights: dict[str, float] | None = None) -> float:
    return _compute.compute_compatibility(source_features, target_features, weights)
