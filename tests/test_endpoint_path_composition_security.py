from __future__ import annotations

import pytest

from processual_api.integrations.enterprise_endpoint_bindings import (
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    build_request_preview,
)


def _binding(path: str = "/customers/{customer_id}") -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="binding.path.security",
        display_name="Path security binding",
        adapter_contract_id="crm",
        task_id="crm.customer_context",
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://sandbox.customer.example/api",
        method="GET",
        path=path,
        required_scope_ids=["crm:read"],
        path_parameters={"customer_id": "$task.customer_id"},
        field_mapping={"customer_id": "$.id"},
    )


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        ("C/102", "C%2F102"),
        ("C?admin=true", "C%3Fadmin%3Dtrue"),
        ("C#fragment", "C%23fragment"),
        ("../admin", "..%2Fadmin"),
        ("C 102", "C%20102"),
        ("C%2F102", "C%252F102"),
    ],
)
def test_task_path_values_are_encoded_as_single_segments(value: str, encoded: str) -> None:
    preview = build_request_preview(_binding(), {"customer_id": value})
    assert preview["url"] == f"https://sandbox.customer.example/api/customers/{encoded}"
    assert preview["network_request_executed"] is False
    assert preview["production_allowed"] is False


def test_empty_path_parameter_is_rejected() -> None:
    with pytest.raises(EndpointBindingError, match="must not be empty"):
        build_request_preview(_binding(), {"customer_id": ""})


def test_unresolved_path_parameter_is_rejected() -> None:
    binding = _binding("/customers/{customer_id}/accounts/{account_id}")
    with pytest.raises(EndpointBindingError, match="unresolved parameters"):
        build_request_preview(binding, {"customer_id": "C-1"})


def test_encoded_path_value_cannot_override_host_or_query() -> None:
    value = "//evil.example/path?token=raw#fragment"
    preview = build_request_preview(_binding(), {"customer_id": value})
    assert preview["url"].startswith("https://sandbox.customer.example/api/customers/")
    assert "evil.example" in preview["url"]
    assert "?token=" not in preview["url"]
    assert "#fragment" not in preview["url"]
    assert "%2F%2Fevil.example%2Fpath%3Ftoken%3Draw%23fragment" in preview["url"]
