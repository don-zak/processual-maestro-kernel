from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
)
from processual_api.routers import settings as settings_module
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as runtime
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    issue_sandbox_execution_grant,
)


def _client() -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "plan_id": "enterprise_core",
    }


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


def _raw() -> dict:
    return {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [_binding()],
    }


def test_live_route_rejects_without_supervisor_grant(monkeypatch) -> None:
    raw = _raw()
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            runtime.execute_enterprise_endpoint_sandbox_proof(
                "billing.account",
                runtime.EndpointSandboxExecuteRequest(
                    task_input={"account_id": "A-100"}
                ),
                _client(),
            )
        )

    assert exc_info.value.status_code == 422
    assert "active sandbox execution grant" in str(exc_info.value.detail)


def test_live_route_persists_only_redacted_evidence(monkeypatch) -> None:
    raw = _raw()
    saved: list[dict] = []
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(
        settings_module,
        "_save_raw",
        lambda user_id, value: saved.append(dict(value)),
    )
    spec = runtime._find_binding(raw, "billing.account")
    grant = issue_sandbox_execution_grant(
        raw,
        spec=spec,
        supervisor_id="supervisor-a",
    )

    async def fake_execute(spec, **kwargs):
        assert kwargs["approval_reference"] == grant["grant_id"]
        return {
            "status": "sandbox_proof_passed",
            "environment": "sandbox",
            "binding_id": spec.binding_id,
            "task_id": spec.task_id,
            "adapter_contract_id": spec.adapter_contract_id,
            "operation_class": "read",
            "required_scope_ids": ["billing:read"],
            "output_slot": "billing_context",
            "canonical_input": {"account_id": "A-100"},
            "canonical_input_sha256": "a" * 64,
            "http_status": 200,
            "content_type": "application/json",
            "destination_host": "sandbox.example.test",
            "resolved_address_count": 1,
            "response_sha256": "b" * 64,
            "approval_reference": grant["grant_id"],
            "credential_source": "deployment_environment_reference",
            "credential_material_included": False,
            "raw_response_included": False,
            "redirects_followed": False,
            "mapping_valid": True,
            "network_request_executed": True,
            "evidence_sha256": "c" * 64,
            "completed_at": "2026-08-10T17:00:00+00:00",
            "production_allowed": False,
            "runtime_connector_approved": False,
            "raw_secret_visible": False,
        }

    monkeypatch.setattr(runtime, "execute_sandbox_binding", fake_execute)
    result = asyncio.run(
        runtime.execute_enterprise_endpoint_sandbox_proof(
            "billing.account",
            runtime.EndpointSandboxExecuteRequest(
                task_input={"account_id": "A-100"}
            ),
            _client(),
        )
    )

    assert result["network_request_executed"] is True
    assert len(saved) == 1
    evidence = raw[runtime.SANDBOX_EVIDENCE_STORAGE_KEY][0]
    assert "canonical_input" not in evidence
    assert evidence["canonical_input_sha256"] == "a" * 64
    assert evidence["raw_response_included"] is False
    assert evidence["raw_secret_visible"] is False
    serialized = repr(evidence).lower()
    assert "bearer " not in serialized
    assert "authorization':" not in serialized
    assert "x-api-key" not in serialized
    assert "api_key_value" not in serialized


def test_evidence_listing_is_customer_safe(monkeypatch) -> None:
    raw = _raw()
    raw[runtime.SANDBOX_EVIDENCE_STORAGE_KEY] = [
        {
            "binding_id": "billing.account",
            "task_id": "billing.account_context",
            "evidence_sha256": "c" * 64,
            "network_request_executed": True,
            "raw_response_included": False,
        }
    ]
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    payload = asyncio.run(
        runtime.list_enterprise_endpoint_sandbox_evidence(_client())
    )
    assert payload["evidence_count"] == 1
    assert payload["production_allowed"] is False
    assert payload["raw_secret_visible"] is False
