from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import LockState


def evaluate_lock_state(
    self_potential: float, transition_gate: float, lock_threshold: float, lock_gate_max: float
) -> LockState:
    return _compute.evaluate_lock_state(self_potential, transition_gate, lock_threshold, lock_gate_max)
