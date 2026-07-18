from __future__ import annotations

import math

from cgtlib.errors import ValidationError
from cgtlib.private import compute as _compute


def compute_phase_mass(probabilities: list[float]) -> float:
    if not probabilities:
        raise ValidationError("probabilities must not be empty")
    for idx, p in enumerate(probabilities):
        if not (0.0 <= p <= 1.0):
            raise ValidationError(f"probabilities[{idx}] must be within [0, 1]")
    return math.fsum(probabilities)


def compute_self_potential(
    phase_mass: float, mean_retention: float, harmony: float, fatigue: float, omega: float
) -> float:
    if phase_mass < 0:
        raise ValidationError("phase_mass must be non-negative")
    if not (0.0 <= mean_retention <= 1.0):
        raise ValidationError("mean_retention must be within [0, 1]")
    if not (0.0 <= harmony <= 1.0):
        raise ValidationError("harmony must be within [0, 1]")
    if fatigue < 0:
        raise ValidationError("fatigue must be non-negative")
    if omega < 0:
        raise ValidationError("omega must be non-negative")
    return _compute.compute_self_potential(phase_mass, mean_retention, harmony, fatigue, omega)
