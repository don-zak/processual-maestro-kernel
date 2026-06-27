from __future__ import annotations

import math
from dataclasses import dataclass

from .catalogs import build_all_canonical_scenario_packs
from .scenarios import ScenarioPack, ScenarioPackResult, evaluate_scenario_pack
from .types import CGTParameters


@dataclass(frozen=True, slots=True)
class TransitionArchetype:
    archetype_id: str
    scenario_id: str
    transition_bias: float
    compatibility_bias: float
    aftermath_bias: float
    tags: tuple[str, ...] = ()
    notes: str = ""


_CANONICAL_ARCHETYPES: tuple[TransitionArchetype, ...] = (
    TransitionArchetype(
        archetype_id="balanced-bridge",
        scenario_id="balanced_transition_band",
        transition_bias=0.0,
        compatibility_bias=0.0,
        aftermath_bias=0.0,
        tags=("canonical", "archetype", "balanced"),
        notes="Reference bridge archetype centered on the balanced canonical band.",
    ),
    TransitionArchetype(
        archetype_id="recovery-arc",
        scenario_id="stress_recovery_band",
        transition_bias=-0.01,
        compatibility_bias=0.01,
        aftermath_bias=0.02,
        tags=("canonical", "archetype", "recovery"),
        notes="Recovery-oriented arc built on the stress-to-recovery canonical band.",
    ),
    TransitionArchetype(
        archetype_id="lock-edge-arc",
        scenario_id="boundary_lock_band",
        transition_bias=-0.02,
        compatibility_bias=-0.01,
        aftermath_bias=-0.02,
        tags=("canonical", "archetype", "edge"),
        notes="Boundary-sensitive arc anchored in the lock-edge canonical band.",
    ),
)


def list_canonical_transition_archetypes() -> tuple[str, ...]:
    return tuple(item.archetype_id for item in _CANONICAL_ARCHETYPES)


def load_canonical_transition_archetype(archetype_id: str) -> TransitionArchetype:
    for item in _CANONICAL_ARCHETYPES:
        if item.archetype_id == archetype_id:
            return item
    raise KeyError(f"unknown transition archetype: {archetype_id}")


def _pack_by_id() -> dict[str, ScenarioPack]:
    return {pack.scenario_id: pack for pack in build_all_canonical_scenario_packs()}


def evaluate_canonical_transition_archetype(
    *,
    base_parameters: CGTParameters,
    archetype_id: str,
) -> tuple[TransitionArchetype, ScenarioPackResult]:
    archetype = load_canonical_transition_archetype(archetype_id)
    pack = _pack_by_id()[archetype.scenario_id]
    result = evaluate_scenario_pack(pack, base_parameters)
    return archetype, result


def evaluate_all_canonical_transition_archetypes(
    *,
    base_parameters: CGTParameters,
) -> tuple[tuple[TransitionArchetype, ScenarioPackResult], ...]:
    pack_by_id = _pack_by_id()
    return tuple(
        (item, evaluate_scenario_pack(pack_by_id[item.scenario_id], base_parameters)) for item in _CANONICAL_ARCHETYPES
    )


def summarize_transition_archetype(
    archetype: TransitionArchetype,
    result: ScenarioPackResult,
) -> dict[str, float]:
    return {
        "transition_center": result.summary["average_transition_channel"],
        "compatibility_center": result.summary["average_compatibility"],
        "aftermath_center": result.summary["average_aftermath_balance"],
        "transition_offset": result.summary["average_transition_channel"] - archetype.transition_bias,
        "compatibility_offset": result.summary["average_compatibility"] - archetype.compatibility_bias,
        "aftermath_offset": result.summary["average_aftermath_balance"] - archetype.aftermath_bias,
        "tag_count": float(len(archetype.tags)),
    }


def summarize_all_transition_archetypes(
    evaluations: tuple[tuple[TransitionArchetype, ScenarioPackResult], ...],
) -> dict[str, float]:
    transition_centers = []
    compatibility_centers = []
    aftermath_centers = []
    for archetype, result in evaluations:
        summary = summarize_transition_archetype(archetype, result)
        transition_centers.append(summary["transition_center"])
        compatibility_centers.append(summary["compatibility_center"])
        aftermath_centers.append(summary["aftermath_center"])
    count = len(evaluations)
    return {
        "archetype_count": float(count),
        "mean_transition_center": math.fsum(transition_centers) / count,
        "mean_compatibility_center": math.fsum(compatibility_centers) / count,
        "mean_aftermath_center": math.fsum(aftermath_centers) / count,
    }
