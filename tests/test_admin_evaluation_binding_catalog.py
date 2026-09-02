from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

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
    sandbox_provisioning_fingerprint,
)
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_binding_catalog as catalog_routes
from processual_api.routers.settings_enterprise_endpoint_bindings_runtime import (
    SANDBOX_EVIDENCE_STORAGE_KEY,
)
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SANDBOX_GRANT_STORAGE_KEY,
)


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "session_type": "identity_user",
        "session_id": "evaluation-session",
    }


def _request() -> Request:
    path = "/settings/admin/evaluation-grants/binding-catalog"
    return Request(
        {
            "type": "http",
            "method": "GET",
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


def _binding() -> EnterpriseEndpointBindingSpec:
    task = get_integration_task("crm.customer_context")
    return EnterpriseEndpointBindingSpec(
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


@pytest.fixture(autouse=True)
def _allow_platform_admin(monkeypatch):
    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    monkeypatch.setattr(catalog_routes, "require_active_platform_admin", allow)


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)


def test_binding_catalog_requires_platform_admin_authority(monkeypatch, tmp_path) -> None:
    _patch_data_dir(monkeypatch, tmp_path)

    async def deny(current_user: dict, request: Request | None = None) -> dict:
        raise HTTPException(status_code=403, detail="platform admin required")

    monkeypatch.setattr(catalog_routes, "require_active_platform_admin", deny)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            catalog_routes.evaluation_binding_catalog(
                request=_request(),
                current_user=_admin(),
            )
        )
    assert exc.value.status_code == 403


def test_binding_catalog_is_subscription_independent_and_fail_closed(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    spec = _binding()
    settings_router._save_raw(
        "evaluation-owner",
        {BINDING_STORAGE_KEY: [spec.model_dump(mode="json")]},
    )

    payload = asyncio.run(
        catalog_routes.evaluation_binding_catalog(
            request=_request(),
            current_user=_admin(),
        )
    )

    assert payload["subscription_required"] is False
    assert payload["commercial_quota_required"] is False
    assert payload["production_allowed"] is False
    assert payload["raw_secret_visible"] is False
    item = payload["bindings"][0]
    assert item["binding_valid"] is True
    assert item["mapping_ready"] is True
    assert item["content_contract_ready"] is False
    assert item["secret_reference_ready"] is False
    assert item["sandbox_readiness"]["sandbox_ready"] is False
    assert item["active_sandbox_grant"] is None
    assert item["selectable"] is False


def test_binding_catalog_exposes_only_safe_ready_projection(monkeypatch, tmp_path) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    spec = _binding()
    content = SandboxContentContract(
        binding_id=spec.binding_id,
        dataset_reference="evaluation_crm_dataset_v1",
        fixture_profile_reference="evaluation_crm_fixture_v1",
        required_record_types=("customer",),
        acceptance_criteria_references=("evaluation_crm_contract_v1",),
    )
    secret_reference = SandboxSecretReference(
        binding_id=spec.binding_id,
        provider_id="customer_vault",
        secret_reference="acme/crm/sandbox-reader",
    )
    provisioning_sha256 = sandbox_provisioning_fingerprint(
        binding=spec.model_dump(mode="json"),
        request_mapping=None,
        secret_reference=secret_reference,
        content_contract=content,
    )
    now = datetime.now(UTC)
    raw = {
        BINDING_STORAGE_KEY: [spec.model_dump(mode="json")],
        SANDBOX_CONTENT_STORAGE_KEY: [content.model_dump(mode="json")],
        SANDBOX_SECRET_REFERENCE_STORAGE_KEY: [secret_reference.model_dump(mode="json")],
        SANDBOX_EVIDENCE_STORAGE_KEY: [
            {
                "binding_id": spec.binding_id,
                "task_id": spec.task_id,
                "operational_proof": True,
                "peer_address_verified": True,
                "customer_secret_reference_configured": True,
                "network_request_executed": True,
                "mapping_valid": True,
                "ready_for_task_consumption": True,
                "provisioning_sha256": provisioning_sha256,
                "evidence_sha256": "a" * 64,
                "production_allowed": False,
                "runtime_connector_approved": False,
                "canonical_input": {"sensitive": "must-not-leak"},
            }
        ],
        SANDBOX_GRANT_STORAGE_KEY: [
            {
                "grant_id": "segrant_evaluation_ready",
                "binding_id": spec.binding_id,
                "task_id": spec.task_id,
                "adapter_contract_id": spec.adapter_contract_id,
                "approved_operation_classes": ["read"],
                "required_scope_ids": list(spec.required_scope_ids),
                "status": "active",
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=30)).isoformat(),
                "issued_by": "supervisor",
            }
        ],
    }
    settings_router._save_raw("evaluation-owner", raw)

    payload = asyncio.run(
        catalog_routes.evaluation_binding_catalog(
            request=_request(),
            current_user=_admin(),
        )
    )
    item = payload["bindings"][0]

    assert item["selectable"] is True
    assert item["sandbox_readiness"]["sandbox_ready"] is True
    assert item["active_sandbox_grant"]["grant_id"] == "segrant_evaluation_ready"
    serialized = str(payload).lower()
    assert "must-not-leak" not in serialized
    assert "canonical_input" not in serialized
    assert "raw_secret" not in serialized.replace("raw_secret_visible", "")
    assert "production_allowed': true" not in serialized
