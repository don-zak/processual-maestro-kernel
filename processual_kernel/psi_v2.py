from __future__ import annotations

import math
from dataclasses import dataclass

from .continuity import clamp
from .types import Coefficients


@dataclass(frozen=True, slots=True)
class PsiV2Parameters:
    """Frozen parameters for bounded continuity shadow qualification."""

    dt: float = 1.0
    decay_lambda: float = 0.05

    def __post_init__(self) -> None:
        if not math.isfinite(self.dt) or self.dt <= 0:
            raise ValueError("dt must be a positive finite number")
        if not math.isfinite(self.decay_lambda) or self.decay_lambda < 0:
            raise ValueError("decay_lambda must be a non-negative finite number")
        if self.decay_lambda * self.dt > 1.0:
            raise ValueError("decay_lambda * dt must be <= 1 for stable explicit updates")


@dataclass(frozen=True, slots=True)
class PsiV2State:
    """Read-only shadow continuity state."""

    psi: float = 0.0
    previous_psi: float = 0.0
    dpsi: float = 0.0
    drive: float = 0.0
    observations: int = 0


class PsiV2Engine:
    """Bounded shadow evaluator that leaves legacy governance unchanged.

    Instantaneous vitality drive:
        G = ((T * N) - C) * exp(-M)

    Shadow continuity state:
        dPsi = (G - lambda * Psi) * dt
        Psi_next = Psi + dPsi

    The separation between drive and dpsi matters: dPsi may be negative
    solely because a high accumulated state relaxes toward equilibrium, even
    while the current operational drive remains positive.
    """

    def __init__(self, params: PsiV2Parameters | None = None):
        self.params = params or PsiV2Parameters()

    @staticmethod
    def drive(coeff: Coefficients) -> float:
        t, n, c, m = clamp(coeff.T), clamp(coeff.N), clamp(coeff.C), clamp(coeff.M)
        return ((t * n) - c) * math.exp(-m)

    def step(self, previous_psi: float, coeff: Coefficients) -> PsiV2State:
        if not math.isfinite(previous_psi):
            previous_psi = 0.0
        drive = self.drive(coeff)
        dpsi = (drive - self.params.decay_lambda * previous_psi) * self.params.dt
        next_psi = previous_psi + dpsi
        return PsiV2State(
            psi=next_psi,
            previous_psi=previous_psi,
            dpsi=dpsi,
            drive=drive,
            observations=1,
        )

    def advance(self, previous: PsiV2State | None, coeff: Coefficients) -> PsiV2State:
        prior = previous or PsiV2State()
        step = self.step(prior.psi, coeff)
        return PsiV2State(
            psi=step.psi,
            previous_psi=step.previous_psi,
            dpsi=step.dpsi,
            drive=step.drive,
            observations=prior.observations + 1,
        )

    @staticmethod
    def as_dict(state: PsiV2State | None) -> dict[str, float | int] | None:
        if state is None:
            return None
        return {
            "psi": state.psi,
            "previous_psi": state.previous_psi,
            "dpsi": state.dpsi,
            "drive": state.drive,
            "observations": state.observations,
        }
