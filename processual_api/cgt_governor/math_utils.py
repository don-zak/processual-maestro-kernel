"""CGT Governor — Math Utilities

Pure numerical helpers used throughout the CGT pipeline:
clamp01, sigmoid, softplus, and linear interpolation.
"""

from __future__ import annotations

import math


def clamp01(x: float) -> float:
    """Clamp value to [0, 1] range."""
    return max(0.0, min(1.0, x))


def sigmoid(x: float) -> float:
    """Standard logistic sigmoid."""
    return 1.0 / (1.0 + math.exp(-x))


def softplus(x: float) -> float:
    """Smooth approximation of ReLU."""
    return math.log(1.0 + math.exp(x))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * clamp01(t)
