from __future__ import annotations

from cgtlib._fallback import compute_compatibility as _compute_compatibility


def compute_compatibility(
    source_features: dict[str, float],
    target_features: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    return _compute_compatibility(source_features, target_features, weights)
