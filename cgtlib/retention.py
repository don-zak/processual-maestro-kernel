from __future__ import annotations

from cgtlib.private import compute as _compute


def compute_retention(transmissibility: float, local_safety: float) -> float:
    return _compute.compute_retention(transmissibility, local_safety)
