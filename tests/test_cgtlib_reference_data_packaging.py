from __future__ import annotations

from cgtlib.reference_data import (
    list_reference_dataset_ids,
    load_all_reference_scenario_records,
    load_reference_scenario_record,
)


def test_reference_dataset_package_is_available() -> None:
    assert list_reference_dataset_ids() == (
        "balanced_transition_band",
        "stress_recovery_band",
        "boundary_lock_band",
    )


def test_reference_dataset_records_load_from_package_resources() -> None:
    records = load_all_reference_scenario_records()

    assert tuple(record.dataset_id for record in records) == (
        "balanced_transition_band",
        "stress_recovery_band",
        "boundary_lock_band",
    )
    assert all(record.scenario_pack.transitions for record in records)


def test_reference_dataset_lookup_preserves_canonical_identity() -> None:
    record = load_reference_scenario_record("boundary_lock_band")

    assert record.dataset_id == "boundary_lock_band"
    assert record.scenario_pack.scenario_id == "boundary_lock_band"
    assert "canonical" in record.scenario_pack.tags
