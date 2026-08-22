from __future__ import annotations

from cgtlib._fallback import compute_retention as _compute_retention


def compute_retention(transmissibility: float, local_safety: float) -> float:
    return _compute_retention(transmissibility, local_safety)
