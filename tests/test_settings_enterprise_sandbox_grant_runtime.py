from __future__ import annotations

import asyncio

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.routers import settings as settings_module
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as runtime
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SANDBOX_GRANT_STORAGE_KEY,
)


def _binding() -> dict:
    return {
        "binding_id": "billing.account",
        "display_name": "Billing account",
        "adapter_contract_id": "billing",
        "task_id": "billing.account_context",
        "credential_profile_id": "enterprise_core_api_reference",
        "environment": "sandbox",
        "base_url": "https://sandbox.example.test/api",
        "method": "GET",
        "path": "/accounts/{account_id}",
        "required_scope_ids": ["billing:read"],
        "path_parameters": {"account_id": "$task.account_id"},
        "query_parameters": {},
        "request_headers": {"Accept": "application/json"},
        "response_format": "json",
        "response_data_path": "$.data",
        "field_mapping": {"account_id": "$.id"},
        "success_codes": [200],
        "timeout_seconds": 15,
    }


def test_supervisor_grant_is_bound_to_client_binding_task_and_scope(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_binding()],
    }
    saved: list[tuple[str, dict]] = []
    monkeypatch.setattr(settings_module, "_load_raw", lambda client_id: raw)
    monkeypatch.setattr(
        settings_module,
        "_save_raw",
        lambda client_id, value: saved.append((client_id, dict(value))),
    )
    monkeypatch.setattr(
        runtime,
        "_require_supervisor_approval_session",
        lambda request: {"key_id": "supervisor-session-key"},
    )

    payload = asyncio.run(
        runtime.grant_enterprise_endpoint_sandbox_execution(
            "client-a",
            "billing.account",
            runtime.EndpointSandboxGrantRequest(ttl_minutes=30),
            object(),
            {"role": "admin", "email": "supervisor@example.test"},
        )
    )

    assert payload["status"] == "sandbox_execution_granted"
    assert payload["supervisor_session_key_id"] == "supervisor-session-key"
    grant = payload["grant"]
    assert grant["binding_id"] == "billing.account"
    assert grant["task_id"] == "billing.account_context"
    assert grant["adapter_contract_id"] == "billing"
    assert grant["approved_operation_classes"] == ["read"]
    assert grant["required_scope_ids"] == ["billing:read"]
    assert grant["issued_by"] == "supervisor@example.test"
    assert grant["production_allowed"] is False
    assert len(saved) == 1
    assert saved[0][0] == "client-a"
    assert raw[SANDBOX_GRANT_STORAGE_KEY][0]["grant_id"] == grant["grant_id"]


def test_supervisor_grant_never_promotes_runtime_or_production(monkeypatch) -> None:
    raw = {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_binding()],
    }
    monkeypatch.setattr(settings_module, "_load_raw", lambda client_id: raw)
    monkeypatch.setattr(settings_module, "_save_raw", lambda client_id, value: None)
    monkeypatch.setattr(
        runtime,
        "_require_supervisor_approval_session",
        lambda request: {"key_id": "supervisor-session-key"},
    )
    payload = asyncio.run(
        runtime.grant_enterprise_endpoint_sandbox_execution(
            "client-a",
            "billing.account",
            runtime.EndpointSandboxGrantRequest(ttl_minutes=5),
            object(),
            {"role": "admin", "user_id": "supervisor-a"},
        )
    )
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["grant"]["production_allowed"] is False
    assert payload["grant"]["runtime_connector_approved"] is False
