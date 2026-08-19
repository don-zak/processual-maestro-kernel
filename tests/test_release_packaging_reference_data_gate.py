from __future__ import annotations

from pathlib import Path


def _release_workflow() -> str:
    return Path(".github/workflows/release.yml").read_text("utf-8")


def test_release_workflow_verifies_reference_data_and_private_exclusion_in_built_wheel() -> None:
    workflow = _release_workflow()

    assert "- name: Verify packaged reference data and private exclusion" in workflow
    assert '"cgtlib/data/reference_scenarios.json" in names' in workflow
    assert 'name.startswith("cgtlib/private/")' in workflow
    assert 'name.startswith("processual_api/private_integrations/")' in workflow


def test_release_workflow_loads_reference_data_and_boundary_from_installed_wheel() -> None:
    workflow = _release_workflow()

    assert "- name: Smoke test installed wheel resources and public boundary" in workflow
    assert "pip install --no-deps dist/*.whl" in workflow
    assert 'load_reference_scenario_record("boundary_lock_band")' in workflow
    assert "assert record.scenario_pack.transitions" in workflow
    assert "assert cgtlib._HAS_PRIVATE is False" in workflow
    assert 'find_spec("cgtlib.private") is None' in workflow
    assert 'find_spec("processual_api.private_integrations") is None' in workflow
    assert "PrivateEvaluationUnavailableError" in workflow
    assert 'str(exc) == "private_evaluation_unavailable"' in workflow


def test_release_workflow_is_not_weaker_than_public_static_and_secret_gates() -> None:
    workflow = _release_workflow()

    assert "- name: Ruff check" in workflow
    assert "- name: Lint (flake8)" in workflow
    assert "- name: Type check (mypy)" in workflow
    assert "- name: Bandit security scan" in workflow
    assert "- name: High-confidence secret scan" in workflow
    assert "python tools/secret_scan.py ." in workflow
    assert "- name: Dependency vulnerability audit" in workflow
    assert "run: pip-audit" in workflow


def test_release_workflow_retains_artifact_dependency_and_license_evidence() -> None:
    workflow = _release_workflow()

    assert "- name: Generate release evidence inventory" in workflow
    assert "python tools/release_evidence_inventory.py" in workflow
    assert "--output release-evidence/release-inventory.json" in workflow
    assert "- name: Upload release evidence" in workflow
    assert "name: release-evidence" in workflow
    assert "path: release-evidence/*" in workflow


def test_release_workflow_retains_cyclonedx_dependency_sbom() -> None:
    workflow = _release_workflow()

    assert "- name: Generate CycloneDX dependency SBOM" in workflow
    assert "pip-audit --format cyclonedx-json" in workflow
    assert "release-evidence/python-environment.cdx.json" in workflow
