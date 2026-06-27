from __future__ import annotations

from .reference_data import list_reference_dataset_ids, load_reference_scenario_record
from .scenarios import ScenarioPack


def list_canonical_scenario_catalog() -> tuple[str, ...]:
    return list_reference_dataset_ids()


def build_canonical_scenario_pack(name: str) -> ScenarioPack:
    return load_reference_scenario_record(name).scenario_pack


def build_all_canonical_scenario_packs() -> tuple[ScenarioPack, ...]:
    return tuple(build_canonical_scenario_pack(name) for name in list_canonical_scenario_catalog())
