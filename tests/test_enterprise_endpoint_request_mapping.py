from __future__ import annotations

import asyncio

import httpx
import pytest

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    EndpointRequestMappingError,
    EnterpriseEndpointRequestMappingSpec,
    build_external_request_body,
    validate_request_mapping,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxCredentialEnvelope,
    execute_sandbox_binding,
)


def _write_binding() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="support.ticket.create",
        display_name="Create sandbox support ticket",
        adapter_contract_id="ticketing",
        task_id="support.ticket_create",
        credential_profile_id="enterprise_core_api_reference",
        environment="sandbox",
        base_url="https://sandbox.example.test/api",
        method="POST",
        path="/tickets",
        required_scope_ids=["ticket:create"],
        request_headers={"Accept": "application/json"},
        response_data_path="$.ticket",
        field_mapping={
            "subject": "$.subject",
            "description": "$.description",
            "customer_id": "$.customer_id",
            "priority": "$.priority",
        },
        success_codes=[201],
    )


def _mapping() -> EnterpriseEndpointRequestMappingSpec:
    return EnterpriseEndpointRequestMappingSpec(
        binding_id="support.ticket.create",
        body_mapping={
            "ticket.subject": "$task.subject",
            "ticket.description": "$task.description",
            "ticket.customer.id": "$task.customer_id",
            "ticket.priority": "$task.priority",
        },
    )


def test_request_mapping_builds_nested_external_json() -> None:
    binding = _write_binding()
    mapping = _mapping()
    validation = validate_request_mapping(binding, mapping)
    assert validation["mapped_body_field_count"] == 4
    assert validation["operation_class"] == "approval_gated_write"

    body = build_external_request_body(
        binding,
        mapping,
        {
            "subject": "Connectivity issue",
            "description": "Sandbox test",
            "customer_id": "C-1",
            "priority": "high",
        },
    )
    assert body == {
        "ticket": {
            "subject": "Connectivity issue",
            "description": "Sandbox test",
            "customer": {"id": "C-1"},
            "priority": "high",
        }
    }


def test_request_mapping_rejects_missing_required_canonical_field() -> None:
    binding = _write_binding()
    mapping = EnterpriseEndpointRequestMappingSpec(
        binding_id=binding.binding_id,
        body_mapping={"ticket.subject": "$task.subject"},
    )
    with pytest.raises(EndpointRequestMappingError, match="omits required"):
        validate_request_mapping(binding, mapping)


def test_get_binding_rejects_request_body_mapping() -> None:
    binding = EnterpriseEndpointBindingSpec(
        binding_id="billing.account",
        display_name="Billing account",
        adapter_contract_id="billing",
        task_id="billing.account_context",
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://sandbox.example.test/api",
        method="GET",
        path="/accounts/{account_id}",
        required_scope_ids=["billing:read"],
        path_parameters={"account_id": "$task.account_id"},
        field_mapping={"account_id": "$.id"},
    )
    mapping = EnterpriseEndpointRequestMappingSpec(
        binding_id=binding.binding_id,
        body_mapping={"account_id": "$task.account_id"},
    )
    with pytest.raises(EndpointRequestMappingError, match="may not define"):
        validate_request_mapping(binding, mapping)


def test_approval_gated_write_crosses_mock_sandbox_with_mapped_body(monkeypatch) -> None:
    async def public_addresses(hostname: str, port: int):
        return ("198.51.100.20",)

    class Resolver:
        async def resolve(self, **kwargs):
            return SandboxCredentialEnvelope(
                headers={"Authorization": "Bearer never-expose"},
                source="test_reference",
            )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer never-expose"
        request_json = __import__("json").loads(request.content)
        assert request_json["ticket"]["subject"] == "Connectivity issue"
        return httpx.Response(
            201,
            json={
                "ticket": {
                    "subject": "Connectivity issue",
                    "description": "Sandbox test",
                    "customer_id": "C-1",
                    "priority": "high",
                }
            },
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    task_input = {
        "subject": "Connectivity issue",
        "description": "Sandbox test",
        "customer_id": "C-1",
        "priority": "high",
    }
    request_body = build_external_request_body(
        _write_binding(),
        _mapping(),
        task_input,
    )
    result = asyncio.run(
        execute_sandbox_binding(
            _write_binding(),
            task_input=task_input,
            request_body=request_body,
            approved_operation_classes={"approval_gated_write"},
            approval_reference="segrant_write",
            credential_resolver=Resolver(),
            transport=httpx.MockTransport(handler),
        )
    )

    assert result["http_status"] == 201
    assert result["network_request_executed"] is True
    assert result["request_body_sha256"]
    assert result["request_body_included_in_evidence"] is False
    assert result["canonical_input"]["subject"] == "Connectivity issue"
    assert "never-expose" not in repr(result)
