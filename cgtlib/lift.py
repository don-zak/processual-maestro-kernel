from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import DynamicLiftState


def compute_dynamic_lift(dwell_time: float, pressure: float, carrier: float, overload: float, *, sensitivity: float = 1.0, dwell_scale: float = 4.0) -> float:
    return _compute.compute_dynamic_lift(dwell_time, pressure, carrier, overload)


def evaluate_dynamic_lift(dwell_time: float, pressure: float, carrier: float, overload: float) -> DynamicLiftState:
    return _compute.evaluate_dynamic_lift(dwell_time, pressure, carrier, overload)
