from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import PossibilityState


def compute_constrained_possibility(raw_potential: float, constraint: float, carrier: float) -> float:
    return _compute.compute_constrained_possibility(raw_potential, constraint, carrier)


def evaluate_possibility(raw_potential: float, constraint: float, carrier: float) -> PossibilityState:
    return _compute.evaluate_possibility(raw_potential, constraint, carrier)
