from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EnterpriseEndpointBindingSpec,
)
from processual_api.routers import settings as settings_router
from processual_api.routers.settings_enterprise_endpoint_bindings_runtime import (
    EndpointMappingPreviewRequest,
    EndpointRequestPreviewRequest,
    delete_enterprise_endpoint_binding,
    get_enterprise_task_catalog,
    list_enterprise_endpoint_bindings,
    preview_enterprise_endpoint_mapping,
    preview_enterprise_endpoint_request,
    save_enterprise_endpoint_binding,
)


def _client(plan_id: str = "enterprise_core") -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "plan_id": plan_id,
    }


def _crm_binding() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="crm.customer.lookup",
        display_name="CRM customer lookup",
        adapter_contract_id="crm",
        task_id="crm.customer_context",
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://sandbox.customer.example/api",
        method="GET",
        path="/customers/{customer_id}",
        required_scope_ids=["crm:read"],
        path_parameters={"customer_id": "$task.customer_id"},
        field_mapping={
            "customer_id": "$.id",
            "customer_name": "$.name",
            "account_status": "$.status",
            "segment": "$.segment",
        },
    )


def test_endpoint_binding_routes_are_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }
    assert "/settings/enterprise-integration/task-catalog" in paths
    assert "/settings/enterprise-integration/endpoint-bindings" in paths
    assert (
        "/settings/enterprise-integration/endpoint-bindings/{binding_id}"
        in paths
    )
    assert (
        "/settings/enterprise-integration/endpoint-bindings/{binding_id}/request-preview"
        in paths
    )
    assert (
        "/settings/enterprise-integration/endpoint-bindings/{binding_id}/mapping-preview"
        in paths
    )


def test_task_catalog_requires_enterprise_entitlement(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {"subscription": {"plan_id": "starter"}},
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_enterprise_task_catalog(_client("starter")))
    assert exc_info.value.status_code == 403


def test_task_catalog_exposes_all_claimed_domain_tasks_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {"subscription": {"plan_id": "enterprise_core"}},
    )
    payload = asyncio.run(get_enterprise_task_catalog(_client()))
    assert payload["task_count"] == 33
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    contract_ids = {task["adapter_contract_id"] for task in payload["tasks"]}
    assert {
        "crm",
        "billing",
        "ticketing",
        "order_management",
        "network_assurance",
        "document",
        "banking_kyc",
        "government_case",
        "research_dataset",
        "university_student",
        "enterprise_helpdesk",
    } == contract_ids


def test_save_and_list_binding_persists_only_safe_endpoint_contract(monkeypatch) -> None:
    raw = {"subscription": {"plan_id": "enterprise_core"}}
    saves: list[dict] = []
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(
        settings_router,
        "_save_raw",
        lambda user_id, data: saves.append(dict(data)),
    )
    body = _crm_binding()
    saved = asyncio.run(
        save_enterprise_endpoint_binding(body.binding_id, body, _client())
    )
    assert saved["status"] == "saved"
    assert saved["persisted"] is True
    assert saved["production_allowed"] is False
    assert saved["runtime_connector_approved"] is False
    assert len(saves) == 1
    assert raw[BINDING_STORAGE_KEY][0]["credential_profile_id"] == (
        "enterprise_core_api_reference"
    )
    stored_text = repr(raw[BINDING_STORAGE_KEY]).lower()
    assert "authorization" not in stored_text
    assert "bearer " not in stored_text
    assert "api_key" not in stored_text

    listed = asyncio.run(list_enterprise_endpoint_bindings(_client()))
    assert listed["binding_count"] == 1
    assert listed["bindings"][0]["binding_id"] == body.binding_id
    assert listed["raw_secret_visible"] is False


def test_save_binding_rejects_path_payload_id_mismatch(monkeypatch) -> None:
    raw = {"subscription": {"plan_id": "enterprise_core"}}
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(settings_router, "_save_raw", lambda user_id, data: None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            save_enterprise_endpoint_binding("different", _crm_binding(), _client())
        )
    assert exc_info.value.status_code == 400
    assert BINDING_STORAGE_KEY not in raw


def test_mapping_preview_injects_canonical_task_input(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_crm_binding().model_dump()],
    }
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    mapped = asyncio.run(
        preview_enterprise_endpoint_mapping(
            "crm.customer.lookup",
            EndpointMappingPreviewRequest(
                response_payload={
                    "id": "C-1",
                    "name": "Example",
                    "status": "active",
                    "segment": "enterprise",
                }
            ),
            _client(),
        )
    )
    assert mapped["output_slot"] == "crm_context"
    assert mapped["canonical_input"]["customer_id"] == "C-1"
    assert mapped["canonical_input"]["account_status"] == "active"
    assert mapped["mapping_valid"] is True
    assert mapped["runtime_connector_approved"] is False


def test_request_preview_builds_sandbox_request_without_network_or_secret(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_crm_binding().model_dump()],
    }
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    preview = asyncio.run(
        preview_enterprise_endpoint_request(
            "crm.customer.lookup",
            EndpointRequestPreviewRequest(task_input={"customer_id": "C-1"}),
            _client(),
        )
    )
    assert preview["url"].endswith("/customers/C-1")
    assert preview["credential_material_included"] is False
    assert preview["network_request_executed"] is False
    assert preview["environment"] == "sandbox"
    assert preview["production_allowed"] is False


def test_delete_binding_removes_only_target_binding(monkeypatch) -> None:
    first = _crm_binding().model_dump()
    second = {**first, "binding_id": "crm.customer.lookup.secondary"}
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [first, second],
    }
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(settings_router, "_save_raw", lambda user_id, data: None)
    payload = asyncio.run(
        delete_enterprise_endpoint_binding("crm.customer.lookup", _client())
    )
    assert payload["status"] == "deleted"
    assert [item["binding_id"] for item in raw[BINDING_STORAGE_KEY]] == [
        "crm.customer.lookup.secondary"
    ]


def test_invalid_stored_binding_is_not_exposed(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [
            {
                **_crm_binding().model_dump(),
                "base_url": "http://unsafe.example",
            }
        ],
    }
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    payload = asyncio.run(list_enterprise_endpoint_bindings(_client()))
    assert payload["binding_count"] == 0
    assert payload["bindings"] == []


def test_locked_plan_cannot_read_or_write_bindings(monkeypatch) -> None:
    raw = {"subscription": {"plan_id": "starter"}}
    monkeypatch.setattr(settings_router, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(settings_router, "_save_raw", lambda user_id, data: None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(list_enterprise_endpoint_bindings(_client("starter")))
    assert exc_info.value.status_code == 403
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            save_enterprise_endpoint_binding(
                _crm_binding().binding_id,
                _crm_binding(),
                _client("starter"),
            )
        )
    assert exc_info.value.status_code == 403
