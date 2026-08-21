from __future__ import annotations

from cgtlib._fallback import (
    compute_constrained_possibility as _compute_constrained_possibility,
    evaluate_possibility as _evaluate_possibility,
)
from cgtlib.types import PossibilityState


def compute_constrained_possibility(raw_potential: float, constraint: float, carrier: float) -> float:
    return _compute_constrained_possibility(raw_potential, constraint, carrier)


def evaluate_possibility(raw_potential: float, constraint: float, carrier: float) -> PossibilityState:
    return _evaluate_possibility(raw_potential, constraint, carrier)
