from __future__ import annotations

import asyncio

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    REQUEST_MAPPING_STORAGE_KEY,
    EnterpriseEndpointRequestMappingSpec,
)
from processual_api.routers import settings as settings_module
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as runtime


def _client() -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "plan_id": "enterprise_core",
    }


def _write_binding() -> dict:
    return {
        "binding_id": "support.ticket.create",
        "display_name": "Create ticket",
        "adapter_contract_id": "ticketing",
        "task_id": "support.ticket_create",
        "credential_profile_id": "enterprise_core_api_reference",
        "environment": "sandbox",
        "base_url": "https://sandbox.example.test/api",
        "method": "POST",
        "path": "/tickets",
        "required_scope_ids": ["ticket:create"],
        "path_parameters": {},
        "query_parameters": {},
        "request_headers": {"Accept": "application/json"},
        "response_format": "json",
        "response_data_path": "$.ticket",
        "field_mapping": {
            "subject": "$.subject",
            "description": "$.description",
        },
        "success_codes": [200, 201],
        "timeout_seconds": 15,
    }


def test_post_binding_reports_request_mapping_blocker_until_configured(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_write_binding()],
    }
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    payload = asyncio.run(
        runtime.get_enterprise_endpoint_request_mapping(
            "support.ticket.create",
            _client(),
        )
    )
    assert payload["configured"] is False
    assert "required canonical task fields" in payload["blocking_reason"]
    assert payload["production_allowed"] is False


def test_request_mapping_save_and_preview_builds_external_body(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_write_binding()],
    }
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(settings_module, "_save_raw", lambda user_id, data: None)
    mapping = EnterpriseEndpointRequestMappingSpec(
        binding_id="support.ticket.create",
        body_mapping={
            "ticket.subject": "$task.subject",
            "ticket.description": "$task.description",
        },
    )
    saved = asyncio.run(
        runtime.save_enterprise_endpoint_request_mapping(
            "support.ticket.create",
            mapping,
            _client(),
        )
    )
    assert saved["status"] == "saved"
    assert raw[REQUEST_MAPPING_STORAGE_KEY][0]["binding_id"] == (
        "support.ticket.create"
    )

    preview = asyncio.run(
        runtime.preview_enterprise_endpoint_request(
            "support.ticket.create",
            runtime.EndpointRequestPreviewRequest(
                task_input={
                    "subject": "Connectivity issue",
                    "description": "Sandbox test",
                }
            ),
            _client(),
        )
    )
    assert preview["request_body"] == {
        "ticket": {
            "subject": "Connectivity issue",
            "description": "Sandbox test",
        }
    }
    assert preview["request_body_includes_credentials"] is False
    assert preview["network_request_executed"] is False
