from __future__ import annotations

import pytest

from processual_api.integrations.endpoint_binding_provenance import (
    EndpointBindingProvenanceError,
    provenance_matches_binding,
    qualify_binding_from_discovery,
)
from processual_api.integrations.endpoint_discovery_quality import assess_endpoint_discovery
from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)


def _binding() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="binding.crm.customer_context",
        display_name="Customer context",
        adapter_contract_id="crm",
        task_id="crm.customer_context",
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://sandbox.customer.example/api",
        method="GET",
        path="/customers/{customer_id}",
        required_scope_ids=["crm:read"],
        path_parameters={"customer_id": "$task.customer_id"},
        field_mapping={"customer_id": "$.id"},
    )


def _assessment() -> dict:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Customer API", "version": "1.4.2"},
        "servers": [{"url": "https://sandbox.customer.example/api/v1"}],
        "paths": {
            "/customers/{customer_id}": {
                "get": {
                    "operationId": "getCustomerContext",
                    "parameters": [
                        {
                            "name": "customer_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Customer context",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                }
            }
        },
    }
    return assess_endpoint_discovery(
        document,
        contract_family="generic_enterprise",
        source_reference="customer-api/releases/v1.4.2/openapi.json",
        release_pinned=True,
        external_references_resolved=True,
    )


def test_exact_discovered_operation_creates_non_production_provenance() -> None:
    spec = _binding()
    provenance = qualify_binding_from_discovery(
        spec,
        _assessment(),
        operation_id="getCustomerContext",
    )

    assert provenance.source_sha256
    assert provenance.operation_id == "getCustomerContext"
    assert provenance.method == "GET"
    assert provenance.path == "/customers/{customer_id}"
    assert provenance.discovery_quality_passed is True
    assert provenance.binding_generation_ready is True
    assert provenance.production_allowed is False
    assert provenance.runtime_connector_approved is False
    assert provenance.raw_secret_visible is False
    assert provenance_matches_binding(spec, provenance) is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("method", "POST", "method_mismatch"),
        ("path", "/customers/{customer_id}/profile", "path_mismatch"),
    ],
)
def test_discovery_rejects_method_or_path_drift(field: str, value: str, message: str) -> None:
    spec = _binding().model_copy(update={field: value})

    with pytest.raises(EndpointBindingProvenanceError, match=message):
        qualify_binding_from_discovery(
            spec,
            _assessment(),
            operation_id="getCustomerContext",
        )


def test_discovery_rejects_unknown_operation_identity() -> None:
    with pytest.raises(EndpointBindingProvenanceError, match="match_exactly_once"):
        qualify_binding_from_discovery(
            _binding(),
            _assessment(),
            operation_id="missingOperation",
        )


def test_discovery_rejects_unqualified_assessment() -> None:
    assessment = {**_assessment(), "binding_generation_ready": False}

    with pytest.raises(EndpointBindingProvenanceError, match="generation_must_be_ready"):
        qualify_binding_from_discovery(
            _binding(),
            assessment,
            operation_id="getCustomerContext",
        )


def test_binding_mutation_invalidates_existing_provenance() -> None:
    spec = _binding()
    provenance = qualify_binding_from_discovery(
        spec,
        _assessment(),
        operation_id="getCustomerContext",
    )

    changed_base_url = spec.model_copy(
        update={"base_url": "https://alternate.customer.example/api"}
    )
    changed_mapping = spec.model_copy(
        update={"query_parameters": {"view": "$task.view"}}
    )

    assert provenance_matches_binding(changed_base_url, provenance) is False
    assert provenance_matches_binding(changed_mapping, provenance) is False


def test_tampered_digest_is_rejected_when_record_is_rehydrated() -> None:
    spec = _binding()
    provenance = qualify_binding_from_discovery(
        spec,
        _assessment(),
        operation_id="getCustomerContext",
    ).model_dump()
    provenance["source_sha256"] = "z" * 64

    with pytest.raises(ValueError, match="SHA-256"):
        provenance_matches_binding(spec, provenance)
