from __future__ import annotations

from dataclasses import dataclass

from .catalogs import build_all_canonical_scenario_packs
from .robustness import RobustnessReport, evaluate_multi_axis_robustness
from .types import CGTParameters


@dataclass(frozen=True, slots=True)
class StressRegime:
    regime_id: str
    axis_grids: dict[str, tuple[float, ...]]
    tags: tuple[str, ...] = ()
    notes: str = ""


_CANONICAL_STRESS_REGIMES: tuple[StressRegime, ...] = (
    StressRegime(
        regime_id="lock_edge_regime",
        axis_grids={
            "lock_threshold": (0.74, 0.78, 0.82),
            "lock_gate_max": (0.10, 0.14, 0.18),
            "lam": (0.86, 0.92, 0.98),
        },
        tags=("canonical", "stress", "lock-edge"),
        notes="Probe edge-lock behavior near restrictive lock activation boundaries.",
    ),
    StressRegime(
        regime_id="gating_overdrive_regime",
        axis_grids={
            "logistic_k": (12.0, 14.0, 16.0),
            "lock_gate_max": (0.22, 0.26, 0.3),
            "mu": (0.84, 0.92, 1.0),
        },
        tags=("canonical", "stress", "gating"),
        notes="Stress high-slope gating and elevated gate saturation sensitivity.",
    ),
    StressRegime(
        regime_id="retention_collapse_regime",
        axis_grids={
            "lam": (0.78, 0.84, 0.9),
            "mu": (0.8, 0.86, 0.92),
            "omega": (0.76, 0.84, 0.92),
        },
        tags=("canonical", "stress", "retention"),
        notes="Probe low-retention, low-support conditions near collapse-like pressure.",
    ),
)


def list_canonical_stress_regimes() -> tuple[str, ...]:
    return tuple(regime.regime_id for regime in _CANONICAL_STRESS_REGIMES)


def load_canonical_stress_regime(regime_id: str) -> StressRegime:
    for regime in _CANONICAL_STRESS_REGIMES:
        if regime.regime_id == regime_id:
            return regime
    raise KeyError(f"unknown stress regime: {regime_id}")


def evaluate_canonical_stress_regime(
    *,
    base_parameters: CGTParameters,
    regime_id: str,
) -> RobustnessReport:
    regime = load_canonical_stress_regime(regime_id)
    packs = list(build_all_canonical_scenario_packs())
    return evaluate_multi_axis_robustness(
        packs,
        base_parameters=base_parameters,
        axis_grids=regime.axis_grids,
    )


def evaluate_all_canonical_stress_regimes(
    *,
    base_parameters: CGTParameters,
) -> tuple[tuple[StressRegime, RobustnessReport], ...]:
    packs = list(build_all_canonical_scenario_packs())
    return tuple(
        (
            regime,
            evaluate_multi_axis_robustness(
                packs,
                base_parameters=base_parameters,
                axis_grids=regime.axis_grids,
            ),
        )
        for regime in _CANONICAL_STRESS_REGIMES
    )
