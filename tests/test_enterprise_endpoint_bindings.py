from __future__ import annotations

import pytest

from processual_api.integrations.enterprise_endpoint_bindings import (
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    build_request_preview,
    map_response_to_task_input,
    safe_binding_payload,
    validate_endpoint_binding,
)
from processual_api.integrations.integration_task_catalog import get_integration_task


PROFILE_BY_CONTRACT = {
    "crm": "enterprise_core_api_reference",
    "billing": "enterprise_core_api_reference",
    "ticketing": "enterprise_core_api_reference",
    "order_management": "enterprise_core_api_reference",
    "network_assurance": "telecom_operations_api_reference",
    "document": "document_repository_reference",
    "banking_kyc": "banking_kyc_api_reference",
    "government_case": "government_case_api_reference",
    "research_dataset": "research_dataset_api_reference",
    "university_student": "university_student_api_reference",
    "enterprise_helpdesk": "enterprise_core_api_reference",
}


def _binding(
    task_id: str,
    *,
    mapping: dict[str, str] | None = None,
    method: str = "GET",
    path: str = "/objects/{object_id}",
) -> EnterpriseEndpointBindingSpec:
    task = get_integration_task(task_id)
    mapping = mapping or {
        field: f"$.{field}" for field in task.required_input_fields
    }
    return EnterpriseEndpointBindingSpec(
        binding_id=f"binding.{task_id}",
        display_name=f"Binding for {task_id}",
        adapter_contract_id=task.adapter_contract_id,
        task_id=task.task_id,
        credential_profile_id=PROFILE_BY_CONTRACT[task.adapter_contract_id],
        base_url="https://sandbox.customer.example/api",
        method=method,
        path=path,
        required_scope_ids=list(task.required_scope_ids),
        path_parameters={"object_id": "$task.object_id"}
        if "{object_id}" in path
        else {},
        field_mapping=mapping,
    )


@pytest.mark.parametrize(
    "task_id",
    [
        "crm.customer_context",
        "billing.account_context",
        "support.ticket_history",
        "order.preview",
        "network.health_context",
        "document.approved_content",
        "banking.kyc_materials",
        "government.case_context",
        "research.dataset_context",
        "university.student_request",
        "enterprise.helpdesk_issue",
    ],
)
def test_each_claimed_domain_accepts_a_schema_valid_endpoint_binding(task_id: str) -> None:
    spec = _binding(task_id, path="/objects")
    payload = validate_endpoint_binding(spec)
    assert payload["lifecycle_state"] == "schema_validated"
    assert payload["environment"] == "sandbox"
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False


def test_response_mapping_produces_canonical_bank_risk_input() -> None:
    spec = _binding(
        "banking.risk_summary",
        path="/risk/cases/{case_id}",
        mapping={
            "case_id": "$.case.reference",
            "risk_indicators": "$.risk.indicators",
            "customer_id": "$.customer.id",
            "risk_status": "$.risk.status",
        },
    ).model_copy(
        update={"path_parameters": {"case_id": "$task.case_id"}}
    )
    response = {
        "case": {"reference": "R-101"},
        "customer": {"id": "C-9"},
        "risk": {"indicators": ["pep_review"], "status": "review"},
    }
    mapped = map_response_to_task_input(spec, response)
    assert mapped["task_id"] == "banking.risk_summary"
    assert mapped["output_slot"] == "risk_context"
    assert mapped["canonical_input"] == {
        "case_id": "R-101",
        "risk_indicators": ["pep_review"],
        "customer_id": "C-9",
        "risk_status": "review",
    }
    assert mapped["mapping_valid"] is True
    assert mapped["production_allowed"] is False


def test_nested_response_data_path_is_supported() -> None:
    spec = _binding(
        "billing.account_context",
        path="/accounts/{account_id}",
        mapping={
            "account_id": "$.id",
            "balance": "$.balance.amount",
            "currency": "$.balance.currency",
        },
    ).model_copy(
        update={
            "path_parameters": {"account_id": "$task.account_id"},
            "response_data_path": "$.data.account",
        }
    )
    mapped = map_response_to_task_input(
        spec,
        {"data": {"account": {"id": "A-7", "balance": {"amount": 42, "currency": "USD"}}}},
    )
    assert mapped["canonical_input"]["account_id"] == "A-7"
    assert mapped["canonical_input"]["balance"] == 42


def test_request_preview_binds_task_parameters_without_credentials() -> None:
    spec = _binding(
        "crm.customer_context",
        path="/customers/{customer_id}",
        mapping={"customer_id": "$.id"},
    ).model_copy(
        update={
            "path_parameters": {"customer_id": "$task.customer_id"},
            "query_parameters": {"include": "$task.include"},
        }
    )
    preview = build_request_preview(
        spec,
        {"customer_id": "C-102", "include": "status"},
    )
    assert preview["method"] == "GET"
    assert preview["url"].endswith("/customers/C-102")
    assert preview["query"] == {"include": "status"}
    assert preview["credential_material_included"] is False
    assert preview["network_request_executed"] is False
    assert preview["production_allowed"] is False


def test_endpoint_binding_rejects_secret_headers() -> None:
    with pytest.raises(ValueError):
        _binding("crm.customer_context", path="/customers").model_copy(
            update={"request_headers": {"Authorization": "Bearer raw-token"}}
        )
        # Pydantic model_copy does not revalidate; force validation explicitly.
        EnterpriseEndpointBindingSpec(
            **{
                **_binding("crm.customer_context", path="/customers").model_dump(),
                "request_headers": {"Authorization": "Bearer raw-token"},
            }
        )


def test_endpoint_binding_rejects_non_https_and_local_targets() -> None:
    base = _binding("crm.customer_context", path="/customers").model_dump()
    with pytest.raises(ValueError):
        EnterpriseEndpointBindingSpec(**{**base, "base_url": "http://example.com"})
    with pytest.raises(ValueError):
        EnterpriseEndpointBindingSpec(**{**base, "base_url": "https://localhost/api"})
    with pytest.raises(ValueError):
        EnterpriseEndpointBindingSpec(**{**base, "base_url": "https://169.254.169.254/latest"})


def test_binding_rejects_task_from_different_adapter_contract() -> None:
    spec = _binding("crm.customer_context", path="/customers")
    invalid = spec.model_copy(update={"adapter_contract_id": "billing"})
    with pytest.raises(EndpointBindingError, match="task is not declared"):
        validate_endpoint_binding(invalid)


def test_binding_rejects_missing_task_required_scope() -> None:
    spec = _binding("banking.risk_summary", path="/risk/cases")
    invalid = spec.model_copy(update={"required_scope_ids": ["risk_case:read"]})
    with pytest.raises(EndpointBindingError, match="omits task-required scopes"):
        validate_endpoint_binding(invalid)


def test_binding_rejects_mapping_outside_canonical_schema() -> None:
    spec = _binding("crm.customer_context", path="/customers")
    invalid = spec.model_copy(
        update={
            "field_mapping": {
                "customer_id": "$.id",
                "raw_password": "$.password",
            }
        }
    )
    with pytest.raises(EndpointBindingError, match="outside canonical task schema"):
        validate_endpoint_binding(invalid)


def test_binding_requires_every_canonical_required_field() -> None:
    spec = _binding(
        "government.request_summary",
        path="/cases",
        mapping={"case_id": "$.id"},
    )
    with pytest.raises(EndpointBindingError, match="omits canonical task fields"):
        validate_endpoint_binding(spec)


def test_safe_binding_payload_never_claims_production_or_runtime_approval() -> None:
    payload = safe_binding_payload(_binding("research.dataset_context", path="/datasets"))
    text = repr(payload).lower()
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False
    assert "authorization" not in text
    assert "bearer " not in text
