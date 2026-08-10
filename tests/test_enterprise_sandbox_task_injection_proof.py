from __future__ import annotations

import asyncio

import httpx

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxCredentialEnvelope,
    execute_sandbox_binding,
)
from processual_api.integrations.integration_task_injection import (
    TASK_INJECTION_SCHEMA_VERSION,
)


class _Resolver:
    async def resolve(self, **kwargs):
        return SandboxCredentialEnvelope(
            headers={"X-API-Key": "never-return-this"},
            source="test_reference",
        )


def test_sandbox_proof_includes_validated_task_injection_digest(monkeypatch) -> None:
    spec = EnterpriseEndpointBindingSpec(
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
        response_data_path="$.data",
        field_mapping={
            "account_id": "$.id",
            "balance": "$.balance",
        },
        success_codes=[200],
    )

    async def public_addresses(hostname: str, port: int):
        return ("198.51.100.20",)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"id": "A-100", "balance": 10}},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    result = asyncio.run(
        execute_sandbox_binding(
            spec,
            task_input={"account_id": "A-100"},
            approved_operation_classes={"read"},
            approval_reference="segrant_test",
            credential_resolver=_Resolver(),
            transport=httpx.MockTransport(handler),
        )
    )

    assert result["status"] == "sandbox_proof_passed"
    assert result["ready_for_task_consumption"] is True
    assert result["task_injection_schema_version"] == TASK_INJECTION_SCHEMA_VERSION
    assert len(result["task_injection_sha256"]) == 64
    assert result["canonical_input_sha256"]
    assert result["network_request_executed"] is True
    assert result["mapping_valid"] is True
    assert "never-return-this" not in repr(result)
