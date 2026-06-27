from __future__ import annotations

from cgtlib.private import compute as _compute
from cgtlib.types import (
    AftermathState,
    CGTParameters,
    LockState,
    PhaseState,
    StructuralTransitionReport,
)


def evaluate_structural_transition(
    source_phase: PhaseState,
    target_phase: PhaseState,
    gate_openness: float,
    carrying_capacity: float,
    node_fatigue: float,
    local_safety: float,
    continuation_channel: float,
    tau: float,
    tau_star: float,
    trigger: float,
    source_features: dict[str, float],
    target_features: dict[str, float],
    params: CGTParameters,
) -> StructuralTransitionReport:
    return _compute.evaluate_structural_transition(
        source_phase=source_phase,
        target_phase=target_phase,
        gate_openness=gate_openness,
        carrying_capacity=carrying_capacity,
        node_fatigue=node_fatigue,
        local_safety=local_safety,
        continuation_channel=continuation_channel,
        tau=tau,
        tau_star=tau_star,
        trigger=trigger,
        source_features=source_features,
        target_features=target_features,
        params=params,
    )


def evaluate_continuation(
    gate_openness: float, carrying_capacity: float, fatigue: float, local_safety: float, lam: float
) -> tuple[float, float]:
    return _compute.evaluate_continuation(gate_openness, carrying_capacity, fatigue, local_safety, lam)


def evaluate_locking(self_potential: float, transition_gate: float, params: CGTParameters) -> LockState:
    return _compute.evaluate_lock_state(self_potential, transition_gate, params.lock_threshold, params.lock_gate_max)


def evaluate_compatibility(
    source_features: dict[str, float], target_features: dict[str, float], weights: dict[str, float] | None = None
) -> float:
    return _compute.compute_compatibility(source_features, target_features, weights)


def evaluate_aftermath(
    target_harmony: float,
    collapse_pressure: float,
    shock: float,
    target_self_potential: float,
    flourishing_factor: float,
) -> AftermathState:
    return _compute.evaluate_aftermath(target_harmony, collapse_pressure, shock, target_self_potential, flourishing_factor)
