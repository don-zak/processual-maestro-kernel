from __future__ import annotations

import pytest

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.routers import settings_endpoint_discovery_qualification_runtime as runtime


def _binding_payload() -> dict:
    return {
        "binding_id": "binding.crm.customer_context",
        "display_name": "Customer context",
        "adapter_contract_id": "crm",
        "task_id": "crm.customer_context",
        "credential_profile_id": "enterprise_core_api_reference",
        "environment": "sandbox",
        "base_url": "https://sandbox.customer.example/api",
        "method": "GET",
        "path": "/customers/{customer_id}",
        "required_scope_ids": ["crm:read"],
        "path_parameters": {"customer_id": "$task.customer_id"},
        "query_parameters": {},
        "request_headers": {},
        "response_format": "json",
        "response_data_path": "$",
        "field_mapping": {"customer_id": "$.id"},
        "success_codes": [200],
        "timeout_seconds": 15,
    }


def _request() -> runtime.EndpointDiscoveryQualificationRequest:
    return runtime.EndpointDiscoveryQualificationRequest(
        api_description={
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
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "object"}
                                    }
                                },
                            }
                        },
                    }
                }
            },
        },
        contract_family="generic_enterprise",
        source_reference="customer-api/releases/v1.4.2/openapi.json",
        release_pinned=True,
        external_references_resolved=True,
        operation_id="getCustomerContext",
    )


@pytest.mark.asyncio
async def test_runtime_persists_safe_provenance_without_raw_api_description(monkeypatch) -> None:
    raw = {BINDING_STORAGE_KEY: [_binding_payload()]}
    saved: dict = {}
    monkeypatch.setattr(runtime, "_require_enterprise", lambda _user: ("client-1", raw))
    monkeypatch.setattr(
        runtime.settings_module,
        "_save_raw",
        lambda user_id, payload: saved.update({"user_id": user_id, "raw": payload}),
    )

    result = await runtime.qualify_endpoint_binding_discovery(
        "binding.crm.customer_context",
        _request(),
        current_user={"sub": "client-1"},
    )

    assert result["status"] == "discovery_qualified"
    assert result["provenance"]["qualification_state"] == "qualified"
    assert result["provenance"]["production_allowed"] is False
    assert saved["user_id"] == "client-1"
    stored = saved["raw"][runtime.DISCOVERY_PROVENANCE_STORAGE_KEY][0]
    assert stored["operation_id"] == "getCustomerContext"
    assert stored["source_sha256"]
    assert "api_description" not in stored
    assert "paths" not in stored


@pytest.mark.asyncio
async def test_runtime_reports_drift_after_binding_mutation(monkeypatch) -> None:
    raw = {BINDING_STORAGE_KEY: [_binding_payload()]}
    monkeypatch.setattr(runtime, "_require_enterprise", lambda _user: ("client-1", raw))
    monkeypatch.setattr(runtime.settings_module, "_save_raw", lambda _user, _raw: None)

    await runtime.qualify_endpoint_binding_discovery(
        "binding.crm.customer_context",
        _request(),
        current_user={"sub": "client-1"},
    )
    raw[BINDING_STORAGE_KEY][0]["base_url"] = "https://alternate.customer.example/api"

    result = await runtime.get_endpoint_discovery_qualification(
        "binding.crm.customer_context",
        current_user={"sub": "client-1"},
    )

    assert result["qualification_state"] == "drifted"
    assert result["provenance_matches_binding"] is False
    assert result["production_allowed"] is False
    assert result["runtime_connector_approved"] is False


@pytest.mark.asyncio
async def test_runtime_returns_not_qualified_without_provenance(monkeypatch) -> None:
    raw = {BINDING_STORAGE_KEY: [_binding_payload()]}
    monkeypatch.setattr(runtime, "_require_enterprise", lambda _user: ("client-1", raw))

    result = await runtime.get_endpoint_discovery_qualification(
        "binding.crm.customer_context",
        current_user={"sub": "client-1"},
    )

    assert result["qualification_state"] == "not_qualified"
    assert result["provenance_matches_binding"] is False
    assert result["production_allowed"] is False
