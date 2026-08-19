from __future__ import annotations

from cgtlib._fallback import (
    compute_delay_gate as _compute_delay_gate,
    compute_transition_channel as _compute_transition_channel,
    compute_transmissibility as _compute_transmissibility,
)


def compute_transmissibility(gate_openness: float, carrying_capacity: float, fatigue: float, lam: float) -> float:
    return _compute_transmissibility(gate_openness, carrying_capacity, fatigue, lam)


def compute_delay_gate(tau: float, tau_star: float, k: float) -> float:
    return _compute_delay_gate(tau, tau_star, k)


def compute_transition_channel(
    continuation_channel: float,
    delay_gate: float,
    trigger: float,
    mu: float,
    compatibility: float,
) -> float:
    return _compute_transition_channel(continuation_channel, delay_gate, trigger, mu, compatibility)
