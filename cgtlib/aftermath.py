from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import AftermathState


def compute_collapse_indicator(target_harmony: float, collapse_pressure: float, shock: float, weights: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> float:
    return _compute.compute_collapse_indicator(target_harmony, collapse_pressure, shock, weights)


def compute_flourishing_indicator(target_harmony: float, target_self_potential: float, flourishing_factor: float, weights: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> float:
    return _compute.compute_flourishing_indicator(target_harmony, target_self_potential, flourishing_factor, weights)


def compute_aftermath_balance(collapse_score: float, flourishing_score: float) -> AftermathState:
    return _compute.compute_aftermath_balance(collapse_score, flourishing_score)
