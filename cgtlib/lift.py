from __future__ import annotations

from cgtlib._fallback import (
    compute_dynamic_lift as _compute_dynamic_lift,
    evaluate_dynamic_lift as _evaluate_dynamic_lift,
)
from cgtlib.types import DynamicLiftState


def compute_dynamic_lift(
    dwell_time: float,
    pressure: float,
    carrier: float,
    overload: float,
    *,
    sensitivity: float = 1.0,
    dwell_scale: float = 4.0,
) -> float:
    return _compute_dynamic_lift(
        dwell_time,
        pressure,
        carrier,
        overload,
        sensitivity=sensitivity,
        dwell_scale=dwell_scale,
    )


def evaluate_dynamic_lift(
    dwell_time: float,
    pressure: float,
    carrier: float,
    overload: float,
) -> DynamicLiftState:
    return _evaluate_dynamic_lift(dwell_time, pressure, carrier, overload)
