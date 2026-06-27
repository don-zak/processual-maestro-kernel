from __future__ import annotations

from dataclasses import dataclass

from .robustness import RobustnessReport, evaluate_multi_axis_robustness
from .scenarios import ScenarioPack
from .types import CGTParameters


@dataclass(frozen=True, slots=True)
class RobustnessProfile:
    profile_id: str
    axis_grids: dict[str, tuple[float, ...]]
    tags: tuple[str, ...] = ()
    notes: str = ""


_CANONICAL_PROFILES: tuple[RobustnessProfile, ...] = (
    RobustnessProfile(
        profile_id="stability_window",
        axis_grids={
            "lam": (0.95, 1.0, 1.05),
            "omega": (0.95, 1.0, 1.05),
            "lock_threshold": (0.68, 0.7, 0.72),
        },
        tags=("canonical", "robustness", "stability"),
        notes="Balanced stability window around the default formal-core parameter center.",
    ),
    RobustnessProfile(
        profile_id="gating_stress_window",
        axis_grids={
            "lock_gate_max": (0.16, 0.2, 0.24),
            "logistic_k": (8.0, 10.0, 12.0),
            "mu": (0.9, 1.0, 1.1),
        },
        tags=("canonical", "robustness", "gating"),
        notes="Stress grid focused on delay gating and lock sensitivity behavior.",
    ),
    RobustnessProfile(
        profile_id="retention_pressure_window",
        axis_grids={
            "lam": (0.9, 1.0, 1.1),
            "mu": (0.92, 1.0, 1.08),
            "omega": (0.9, 1.0, 1.1),
        },
        tags=("canonical", "robustness", "pressure"),
        notes="Pressure grid probing retention and transition balance under coupled drift.",
    ),
)


def list_canonical_robustness_profiles() -> tuple[str, ...]:
    return tuple(profile.profile_id for profile in _CANONICAL_PROFILES)


def load_canonical_robustness_profile(profile_id: str) -> RobustnessProfile:
    for profile in _CANONICAL_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(f"unknown robustness profile: {profile_id}")


def evaluate_canonical_robustness_profile(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
    profile_id: str,
) -> RobustnessReport:
    profile = load_canonical_robustness_profile(profile_id)
    return evaluate_multi_axis_robustness(
        packs,
        base_parameters=base_parameters,
        axis_grids=profile.axis_grids,
    )


def evaluate_all_canonical_robustness_profiles(
    packs: list[ScenarioPack],
    *,
    base_parameters: CGTParameters,
) -> tuple[tuple[RobustnessProfile, RobustnessReport], ...]:
    return tuple(
        (
            profile,
            evaluate_multi_axis_robustness(
                packs,
                base_parameters=base_parameters,
                axis_grids=profile.axis_grids,
            ),
        )
        for profile in _CANONICAL_PROFILES
    )
