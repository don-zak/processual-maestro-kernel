from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from .batch import StructuralTransitionInput
from .fixtures import canonical_phase_state, canonical_scenario_pack, canonical_transition_input
from .scenarios import ScenarioPack

_DATA_PACKAGE = "cgtlib.data"
_DATA_RESOURCE = "reference_scenarios.json"


@dataclass(frozen=True, slots=True)
class ReferenceScenarioRecord:
    dataset_id: str
    scenario_pack: ScenarioPack
    notes: str = ""


def _load_payload() -> dict[str, object]:
    with resources.files(_DATA_PACKAGE).joinpath(_DATA_RESOURCE).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _phase_from_payload(payload: dict[str, float | str]) -> object:
    return canonical_phase_state(
        str(payload["phase_id"]),
        mass=float(payload["mass"]),
        mean_retention=float(payload["mean_retention"]),
        harmony=float(payload["harmony"]),
        fatigue=float(payload["fatigue"]),
        self_potential=float(payload["self_potential"]) if payload.get("self_potential") is not None else None,
    )


def _transition_from_payload(payload: dict[str, object]) -> StructuralTransitionInput:
    source_phase = _phase_from_payload(dict(payload["source_phase"]))
    target_phase = _phase_from_payload(dict(payload["target_phase"]))
    source_features = payload.get("source_features")
    target_features = payload.get("target_features")
    return canonical_transition_input(
        source_phase=source_phase,
        target_phase=target_phase,
        gate_openness=float(payload["gate_openness"]),
        carrying_capacity=float(payload["carrying_capacity"]),
        node_fatigue=float(payload["node_fatigue"]),
        local_safety=float(payload["local_safety"]),
        continuation_channel=float(payload["continuation_channel"]),
        tau=float(payload["tau"]),
        tau_star=float(payload["tau_star"]),
        trigger=float(payload["trigger"]),
        source_features={str(key): float(value) for key, value in dict(source_features).items()}
        if source_features is not None
        else None,
        target_features={str(key): float(value) for key, value in dict(target_features).items()}
        if target_features is not None
        else None,
    )


def list_reference_dataset_ids() -> tuple[str, ...]:
    payload = _load_payload()
    return tuple(str(record["dataset_id"]) for record in payload["datasets"])


def load_reference_scenario_record(dataset_id: str) -> ReferenceScenarioRecord:
    payload = _load_payload()
    for record in payload["datasets"]:
        if str(record["dataset_id"]) != dataset_id:
            continue
        transitions = tuple(_transition_from_payload(dict(item)) for item in record["transitions"])
        scenario_pack = canonical_scenario_pack(
            scenario_id=str(record["dataset_id"]),
            transitions=transitions,
            tags=tuple(str(tag) for tag in record.get("tags", ("formal-core", "canonical", "dataset"))),
            notes=str(record.get("notes", "")),
        )
        return ReferenceScenarioRecord(
            dataset_id=str(record["dataset_id"]),
            scenario_pack=scenario_pack,
            notes=str(record.get("notes", "")),
        )
    raise KeyError(f"unknown reference dataset: {dataset_id}")


def load_all_reference_scenario_records() -> tuple[ReferenceScenarioRecord, ...]:
    return tuple(load_reference_scenario_record(dataset_id) for dataset_id in list_reference_dataset_ids())


def load_reference_scenario_packs() -> tuple[ScenarioPack, ...]:
    return tuple(record.scenario_pack for record in load_all_reference_scenario_records())
