from __future__ import annotations

from .batch import StructuralTransitionInput
from .scenarios import ScenarioPack
from .types import PhaseState


def canonical_phase_state(
    name: str,
    *,
    mass: float,
    mean_retention: float,
    harmony: float,
    fatigue: float,
    self_potential: float | None = None,
) -> PhaseState:
    return PhaseState(
        phase_id=name,
        mass=mass,
        mean_retention=mean_retention,
        harmony=harmony,
        fatigue=fatigue,
        self_potential=self_potential,
    )


def canonical_transition_input(
    *,
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
    source_features: dict[str, float] | None = None,
    target_features: dict[str, float] | None = None,
) -> StructuralTransitionInput:
    if source_features is None:
        source_features = {
            "mass": min(1.0, source_phase.mass),
            "harmony": source_phase.harmony,
            "continuation": continuation_channel,
            "absorption": source_phase.mean_retention,
        }
    if target_features is None:
        target_features = {
            "mass": min(1.0, target_phase.mass),
            "harmony": target_phase.harmony,
            "continuation": continuation_channel,
            "absorption": target_phase.mean_retention,
        }
    return StructuralTransitionInput(
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
    )


def canonical_scenario_pack(
    scenario_id: str,
    transitions: tuple[StructuralTransitionInput, ...],
    *,
    tags: tuple[str, ...] = ("formal-core", "canonical"),
    notes: str = "canonical formal-core scenario pack",
) -> ScenarioPack:
    return ScenarioPack(
        scenario_id=scenario_id,
        transitions=transitions,
        tags=tags,
        notes=notes,
    )
