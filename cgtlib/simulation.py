from __future__ import annotations

import math

from .gates import compute_delay_gate
from .types import StructuralTransitionReport
from .validation import ensure_not_empty


def simulate_delay_progression(taus: list[float], tau_star: float, k: float) -> list[float]:
    ensure_not_empty(taus, "taus")
    return [compute_delay_gate(tau, tau_star, k) for tau in taus]


def simulate_transition_series(reports: list[StructuralTransitionReport]) -> dict[str, float]:
    ensure_not_empty(reports, "reports")
    count = len(reports)
    avg_transition = math.fsum(report.transition_channel for report in reports) / count
    avg_compatibility = math.fsum(report.compatibility for report in reports) / count
    avg_balance = math.fsum(report.aftermath.balance for report in reports) / count
    return {
        "count": float(count),
        "average_transition_channel": avg_transition,
        "average_compatibility": avg_compatibility,
        "average_aftermath_balance": avg_balance,
    }
