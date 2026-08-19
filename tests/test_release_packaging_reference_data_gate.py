from __future__ import annotations

from pathlib import Path


def test_release_workflow_verifies_reference_data_in_built_wheel() -> None:
    workflow = Path(".github/workflows/release.yml").read_text("utf-8")

    assert "- name: Verify packaged reference data" in workflow
    assert '"cgtlib/data/reference_scenarios.json" in archive.namelist()' in workflow


def test_release_workflow_loads_reference_data_from_installed_wheel() -> None:
    workflow = Path(".github/workflows/release.yml").read_text("utf-8")

    assert "- name: Smoke test installed wheel resources" in workflow
    assert "pip install --no-deps dist/*.whl" in workflow
    assert 'load_reference_scenario_record("boundary_lock_band")' in workflow
    assert "assert record.scenario_pack.transitions" in workflow
