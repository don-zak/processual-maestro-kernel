"""Contract validation for six isolated university/government demo bindings."""
from __future__ import annotations

import pytest

from processual_api.integrations.enterprise_endpoint_bindings import validate_endpoint_binding
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    build_external_request_body, validate_request_mapping,
)
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.services.evaluation_owned_sector_presets import sector_presets

BASE_URL = "https://sandbox.example.invalid"


def test_six_sector_presets_validate_against_canonical_contracts() -> None:
    presets = sector_presets(BASE_URL)
    assert len(presets) == 6
    assert len({preset.binding.binding_id for preset in presets}) == 6
    assert len({preset.scenario_id for preset in presets}) == 6
    assert sum(preset.binding.method == "POST" for preset in presets) == 2
    for preset in presets:
        binding = preset.binding
        validation = validate_endpoint_binding(binding)
        task = get_integration_task(binding.task_id)
        assert validation["environment"] == "sandbox"
        assert validation["production_allowed"] is False
        assert binding.required_scope_ids == list(task.required_scope_ids)
        assert set(task.required_input_fields).issubset(binding.field_mapping)
        assert preset.content_contract.project_owned is True
        assert preset.content_contract.synthetic_or_nonproduction is True
        assert preset.content_contract.secrets_included is False
        assert preset.secret_reference.value_included is False
        assert preset.secret_reference.project_scoped is True


def test_post_draft_request_mapping_covers_required_fields() -> None:
    for preset in sector_presets(BASE_URL):
        if preset.binding.method == "GET":
            assert preset.request_mapping is None
            continue
        mapping = preset.request_mapping
        assert mapping is not None
        validated = validate_request_mapping(preset.binding, mapping)
        task = get_integration_task(preset.binding.task_id)
        assert validated["mapped_body_field_count"] == len(task.required_input_fields)
        body = build_external_request_body(preset.binding, mapping, preset.sample_input)
        assert isinstance(body, dict)
        assert all(body[field] == preset.sample_input[field] for field in task.required_input_fields)


def test_binding_templates_reject_non_https_or_private_hosts() -> None:
    with pytest.raises(ValueError):
        sector_presets("http://localhost:8787")
    with pytest.raises(ValueError):
        sector_presets("https://localhost")


def test_no_cross_sector_preset_binding_or_secret_material() -> None:
    presets = sector_presets(BASE_URL)
    for item in presets:
        sector = "university" if item.scenario_id.startswith("UNI-") else "government"
        assert item.binding.task_id.startswith(sector + ".")
        assert sector in item.binding.binding_id
        assert item.secret_reference.secret_reference == "public"
        assert not item.binding.request_headers
        assert item.binding.environment == "sandbox"
