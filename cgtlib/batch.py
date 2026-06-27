from __future__ import annotations

from dataclasses import dataclass

from .evaluators import evaluate_structural_transition
from .invariants import validate_parameters, validate_phase_state, validate_structural_transition_report
from .simulation import simulate_transition_series
from .types import CGTParameters, PhaseState, StructuralTransitionReport
from .validation import ensure_not_empty, ensure_unit_interval


@dataclass(frozen=True, slots=True)
class StructuralTransitionInput:
    source_phase: PhaseState
    target_phase: PhaseState
    gate_openness: float
    carrying_capacity: float
    node_fatigue: float
    local_safety: float
    continuation_channel: float
    tau: float
    tau_star: float
    trigger: float
    source_features: dict[str, float]
    target_features: dict[str, float]


def evaluate_transition_batch(
    inputs: list[StructuralTransitionInput],
    params: CGTParameters,
) -> list[StructuralTransitionReport]:
    ensure_not_empty(inputs, "inputs")
    validate_parameters(params)
    return [
        validate_structural_transition_report(
            evaluate_structural_transition(
                source_phase=item.source_phase,
                target_phase=item.target_phase,
                gate_openness=item.gate_openness,
                carrying_capacity=item.carrying_capacity,
                node_fatigue=item.node_fatigue,
                local_safety=item.local_safety,
                continuation_channel=item.continuation_channel,
                tau=item.tau,
                tau_star=item.tau_star,
                trigger=item.trigger,
                source_features=item.source_features,
                target_features=item.target_features,
                params=params,
            )
        )
        for item in inputs
    ]


def summarize_transition_batch(inputs: list[StructuralTransitionInput], params: CGTParameters) -> dict[str, float]:
    reports = evaluate_transition_batch(inputs, params)
    return simulate_transition_series(reports)


def validate_transition_batch_inputs(inputs: list[StructuralTransitionInput]) -> list[StructuralTransitionInput]:
    ensure_not_empty(inputs, "inputs")
    for index, item in enumerate(inputs):
        validate_phase_state(item.source_phase)
        validate_phase_state(item.target_phase)
        ensure_unit_interval(item.gate_openness, f"inputs[{index}].gate_openness")
        ensure_unit_interval(item.carrying_capacity, f"inputs[{index}].carrying_capacity")
        ensure_unit_interval(item.local_safety, f"inputs[{index}].local_safety")
        ensure_unit_interval(item.continuation_channel, f"inputs[{index}].continuation_channel")
    return inputs
