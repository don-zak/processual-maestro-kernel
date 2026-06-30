from __future__ import annotations

from cgtlib.private import compute as _compute


def compute_transmissibility(gate_openness: float, carrying_capacity: float, fatigue: float, lam: float) -> float:
    return _compute.compute_transmissibility(gate_openness, carrying_capacity, fatigue, lam)


def compute_delay_gate(tau: float, tau_star: float, k: float) -> float:
    return _compute.compute_delay_gate(tau, tau_star, k)


def compute_transition_channel(
    continuation_channel: float, delay_gate: float, trigger: float, mu: float, compatibility: float
) -> float:
    return _compute.compute_transition_channel(continuation_channel, delay_gate, trigger, mu, compatibility)
