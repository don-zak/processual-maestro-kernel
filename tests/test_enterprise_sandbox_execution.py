from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxCredentialEnvelope,
    SandboxExecutionError,
    execute_sandbox_binding,
)


class _Resolver:
    async def resolve(self, *, credential_profile_id: str, binding_id: str):
        assert credential_profile_id == "enterprise_core_api_reference"
        assert binding_id == "billing.account"
        return SandboxCredentialEnvelope(
            headers={"Authorization": "Bearer should-never-leak"},
            source="test_reference",
        )


def _spec() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="billing.account",
        display_name="Billing account",
        adapter_contract_id="billing",
        task_id="billing.account_context",
        credential_profile_id="enterprise_core_api_reference",
        environment="sandbox",
        base_url="https://sandbox.example.test/api",
        method="GET",
        path="/accounts/{account_id}",
        required_scope_ids=["billing:read"],
        path_parameters={"account_id": "$task.account_id"},
        request_headers={"Accept": "application/json"},
        response_data_path="$.data",
        field_mapping={
            "account_id": "$.id",
            "balance": "$.balance",
            "currency": "$.currency",
        },
        success_codes=[200],
    )


def _transport(status: int = 200, *, content_type: str = "application/json"):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer should-never-leak"
        assert str(request.url).startswith(
            "https://sandbox.example.test/api/accounts/A-100"
        )
        return httpx.Response(
            status,
            json={
                "data": {
                    "id": "A-100",
                    "balance": 42.5,
                    "currency": "USD",
                }
            },
            headers={"content-type": content_type},
        )

    return httpx.MockTransport(handler)


def test_live_sandbox_execution_returns_canonical_proof(monkeypatch) -> None:
    async def public_addresses(hostname: str, port: int):
        assert hostname == "sandbox.example.test"
        assert port == 443
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    result = asyncio.run(
        execute_sandbox_binding(
            _spec(),
            task_input={"account_id": "A-100"},
            approved_operation_classes={"read"},
            approval_reference="segrant_test",
            credential_resolver=_Resolver(),
            transport=_transport(),
            now=datetime(2026, 8, 10, 17, 0, tzinfo=UTC),
        )
    )

    assert result["status"] == "sandbox_proof_passed"
    assert result["network_request_executed"] is True
    assert result["mapping_valid"] is True
    assert result["canonical_input"] == {
        "account_id": "A-100",
        "balance": 42.5,
        "currency": "USD",
    }
    assert len(result["canonical_input_sha256"]) == 64
    assert len(result["response_sha256"]) == 64
    assert len(result["evidence_sha256"]) == 64
    assert result["credential_material_included"] is False
    assert result["raw_response_included"] is False
    assert result["redirects_followed"] is False
    assert result["production_allowed"] is False
    assert result["runtime_connector_approved"] is False
    assert "should-never-leak" not in repr(result)


def test_execution_requires_exact_approved_operation_class(monkeypatch) -> None:
    async def public_addresses(hostname: str, port: int):
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    with pytest.raises(SandboxExecutionError, match="operation_class_not_approved"):
        asyncio.run(
            execute_sandbox_binding(
                _spec(),
                task_input={"account_id": "A-100"},
                approved_operation_classes={"draft"},
                approval_reference="segrant_test",
                credential_resolver=_Resolver(),
                transport=_transport(),
            )
        )


def test_redirect_is_blocked(monkeypatch) -> None:
    async def public_addresses(hostname: str, port: int):
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"location": "https://other.example.test/"},
        )
    )
    with pytest.raises(SandboxExecutionError, match="redirect_blocked"):
        asyncio.run(
            execute_sandbox_binding(
                _spec(),
                task_input={"account_id": "A-100"},
                approved_operation_classes={"read"},
                approval_reference="segrant_test",
                credential_resolver=_Resolver(),
                transport=transport,
            )
        )


def test_non_json_response_is_blocked(monkeypatch) -> None:
    async def public_addresses(hostname: str, port: int):
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        public_addresses,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            text="not json",
            headers={"content-type": "text/plain"},
        )
    )
    with pytest.raises(SandboxExecutionError, match="response_not_json"):
        asyncio.run(
            execute_sandbox_binding(
                _spec(),
                task_input={"account_id": "A-100"},
                approved_operation_classes={"read"},
                approval_reference="segrant_test",
                credential_resolver=_Resolver(),
                transport=transport,
            )
        )


def test_dns_guard_rejection_occurs_before_credentials(monkeypatch) -> None:
    calls = 0

    async def blocked(hostname: str, port: int):
        raise SandboxExecutionError("sandbox_destination_not_public")

    class NeverResolver:
        async def resolve(self, **kwargs):
            nonlocal calls
            calls += 1
            raise AssertionError("credentials must not be resolved")

    monkeypatch.setattr(
        "processual_api.integrations.enterprise_sandbox_execution.resolve_public_addresses",
        blocked,
    )
    with pytest.raises(SandboxExecutionError, match="destination_not_public"):
        asyncio.run(
            execute_sandbox_binding(
                _spec(),
                task_input={"account_id": "A-100"},
                approved_operation_classes={"read"},
                approval_reference="segrant_test",
                credential_resolver=NeverResolver(),
                transport=_transport(),
            )
        )
    assert calls == 0
