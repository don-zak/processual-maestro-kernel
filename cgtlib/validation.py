from __future__ import annotations

import math
from collections.abc import Sequence

from .constants import MAX_PROBABILITY, MIN_PROBABILITY
from .errors import ValidationError


def _ensure_finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValidationError(f"{name} must be finite")
    return value


def ensure_unit_interval(value: float, name: str) -> float:
    value = _ensure_finite(value, name)
    if value < MIN_PROBABILITY or value > MAX_PROBABILITY:
        raise ValidationError(f"{name} must be within [0, 1]")
    return value


def ensure_nonnegative(value: float, name: str) -> float:
    value = _ensure_finite(value, name)
    if value < 0:
        raise ValidationError(f"{name} must be non-negative")
    return value


def ensure_not_empty(seq: Sequence[object], name: str):
    if not seq:
        raise ValidationError(f"{name} must not be empty")
    return seq


def ensure_same_keys(a: dict, b: dict, name_a: str, name_b: str):
    if set(a.keys()) != set(b.keys()):
        raise ValidationError(f"{name_a} and {name_b} must have the same keys")
    return a, b
