from __future__ import annotations

from cgtlib._fallback import (
    compute_existential_score as _compute_existential_score,
    evaluate_existence as _evaluate_existence,
)
from cgtlib.types import ExistenceState


def compute_existential_score(
    origin: float,
    carrier: float,
    effect: float,
    *,
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
    threshold: float = 0.35,
    sharpness: float = 8.0,
) -> float:
    return _compute_existential_score(
        origin,
        carrier,
        effect,
        weights=weights,
        threshold=threshold,
        sharpness=sharpness,
    )


def evaluate_existence(origin: float, carrier: float, effect: float) -> ExistenceState:
    return _evaluate_existence(origin, carrier, effect)
