from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
)
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_binding_provisioning as routes
from processual_api.services.enterprise_endpoint_sandbox_grants import SANDBOX_GRANT_STORAGE_KEY


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "session_type": "identity_user",
        "session_id": "evaluation-session",
    }


def _request() -> Request:
    path = "/settings/admin/evaluation-grants/bindings/evaluation.crm.customer/provision"
    return Request(
        {
            "type": "http",
            "method": "PUT",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _body() -> routes.EvaluationBindingProvisionRequest:
    task = get_integration_task("crm.customer_context")
    binding = EnterpriseEndpointBindingSpec(
        binding_id="evaluation.crm.customer",
        display_name="Evaluation CRM customer context",
        adapter_contract_id=task.adapter_contract_id,
        task_id=task.task_id,
        credential_profile_id="enterprise_core_api_reference",
        base_url="https://sandbox.customer.example/api",
        method="GET",
        path="/customers",
        required_scope_ids=list(task.required_scope_ids),
        field_mapping={field: f"$.{field}" for field in task.required_input_fields},
    )
    return routes.EvaluationBindingProvisionRequest(
        binding=binding,
        content_contract=SandboxContentContract(
            binding_id=binding.binding_id,
            dataset_reference="evaluation_crm_dataset_v1",
            fixture_profile_reference="evaluation_crm_fixture_v1",
            required_record_types=("customer",),
            acceptance_criteria_references=("evaluation_crm_contract_v1",),
        ),
        secret_reference=SandboxSecretReference(
            binding_id=binding.binding_id,
            provider_id="customer_vault",
            secret_reference="acme/crm/sandbox-reader",
        ),
        ttl_minutes=30,
    )


@pytest.fixture(autouse=True)
def _allow_platform_admin(monkeypatch):
    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    monkeypatch.setattr(routes, "require_active_platform_admin", allow)


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)


def test_provisioning_requires_platform_admin(monkeypatch, tmp_path) -> None:
    _patch_data_dir(monkeypatch, tmp_path)

    async def deny(current_user: dict, request: Request | None = None) -> dict:
        raise HTTPException(status_code=403, detail="platform admin required")

    monkeypatch.setattr(routes, "require_active_platform_admin", deny)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.provision_evaluation_binding(
                binding_id="evaluation.crm.customer",
                body=_body(),
                request=_request(),
                current_user=_admin(),
            )
        )
    assert exc.value.status_code == 403


def test_provisioning_is_subscription_independent_and_persists_safe_authority(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_data_dir(monkeypatch, tmp_path)

    def issue(raw, *, spec, supervisor_id, ttl_minutes):
        grant = {
            "grant_id": "segrant_eval_001",
            "binding_id": spec.binding_id,
            "task_id": spec.task_id,
            "adapter_contract_id": spec.adapter_contract_id,
            "approved_operation_classes": ["read"],
            "required_scope_ids": list(spec.required_scope_ids),
            "status": "active",
            "issued_at": "2026-09-01T08:00:00+00:00",
            "expires_at": "2026-09-01T08:30:00+00:00",
            "issued_by": supervisor_id,
            "production_allowed": False,
        }
        raw[SANDBOX_GRANT_STORAGE_KEY] = [grant]
        return grant

    monkeypatch.setattr(routes, "issue_sandbox_execution_grant", issue)

    payload = asyncio.run(
        routes.provision_evaluation_binding(
            binding_id="evaluation.crm.customer",
            body=_body(),
            request=_request(),
            current_user=_admin(),
        )
    )

    assert payload["status"] == "provisioned"
    assert payload["subscription_required"] is False
    assert payload["registration_required"] is False
    assert payload["commercial_quota_required"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["raw_secret_visible"] is False
    assert payload["raw_payload_visible"] is False

    raw = settings_router._load_raw("evaluation-owner")
    assert raw[BINDING_STORAGE_KEY][0]["binding_id"] == "evaluation.crm.customer"
    assert raw[SANDBOX_CONTENT_STORAGE_KEY][0]["binding_id"] == "evaluation.crm.customer"
    assert raw[SANDBOX_SECRET_REFERENCE_STORAGE_KEY][0]["binding_id"] == "evaluation.crm.customer"
    assert raw[SANDBOX_GRANT_STORAGE_KEY][0]["grant_id"] == "segrant_eval_001"

    serialized = str(payload).lower()
    assert "acme/crm/sandbox-reader" not in serialized
    assert "production_allowed': true" not in serialized


def test_provisioning_rejects_mismatched_binding_ids(monkeypatch, tmp_path) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    body = _body()
    body.content_contract.binding_id = "evaluation.crm.other"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.provision_evaluation_binding(
                binding_id="evaluation.crm.customer",
                body=body,
                request=_request(),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 400
    assert "content contract" in str(exc.value.detail)


def test_post_binding_requires_request_mapping_before_persistence(monkeypatch, tmp_path) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    body = _body()
    body.binding.method = "POST"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.provision_evaluation_binding(
                binding_id="evaluation.crm.customer",
                body=body,
                request=_request(),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 422
    assert "request body mapping is required" in str(exc.value.detail)
    assert settings_router._load_raw("evaluation-owner").get(BINDING_STORAGE_KEY) is None
