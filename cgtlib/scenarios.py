from __future__ import annotations

import math
from dataclasses import dataclass

from .batch import (
    StructuralTransitionInput,
    evaluate_transition_batch,
    summarize_transition_batch,
    validate_transition_batch_inputs,
)
from .errors import ValidationError
from .invariants import validate_parameters
from .types import CGTParameters, StructuralTransitionReport
from .validation import ensure_not_empty


@dataclass(frozen=True, slots=True)
class ScenarioPack:
    scenario_id: str
    transitions: tuple[StructuralTransitionInput, ...]
    tags: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ScenarioPackResult:
    scenario_id: str
    reports: tuple[StructuralTransitionReport, ...]
    summary: dict[str, float]
    tags: tuple[str, ...] = ()


def validate_scenario_pack(pack: ScenarioPack) -> ScenarioPack:
    if not pack.scenario_id.strip():
        raise ValidationError("scenario_id must not be empty")
    ensure_not_empty(list(pack.transitions), "transitions")
    validate_transition_batch_inputs(list(pack.transitions))
    return pack


def evaluate_scenario_pack(pack: ScenarioPack, params: CGTParameters) -> ScenarioPackResult:
    validate_parameters(params)
    validated = validate_scenario_pack(pack)
    reports = tuple(evaluate_transition_batch(list(validated.transitions), params))
    summary = summarize_transition_batch(list(validated.transitions), params)
    return ScenarioPackResult(
        scenario_id=validated.scenario_id,
        reports=reports,
        summary=summary,
        tags=validated.tags,
    )


def evaluate_scenario_packs(packs: list[ScenarioPack], params: CGTParameters) -> list[ScenarioPackResult]:
    ensure_not_empty(packs, "packs")
    validate_parameters(params)
    return [evaluate_scenario_pack(pack, params) for pack in packs]


def summarize_scenario_packs(results: list[ScenarioPackResult]) -> dict[str, float]:
    ensure_not_empty(results, "results")
    transition_means = [result.summary["average_transition_channel"] for result in results]
    compatibility_means = [result.summary["average_compatibility"] for result in results]
    balance_means = [result.summary["average_aftermath_balance"] for result in results]
    return {
        "scenario_count": float(len(results)),
        "mean_transition_channel": math.fsum(transition_means) / len(transition_means),
        "mean_compatibility": math.fsum(compatibility_means) / len(compatibility_means),
        "mean_aftermath_balance": math.fsum(balance_means) / len(balance_means),
    }
