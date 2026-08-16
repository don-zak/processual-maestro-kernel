from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    EnterpriseEndpointBindingSpec,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    REQUEST_MAPPING_STORAGE_KEY,
    EnterpriseEndpointRequestMappingSpec,
)
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
)
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_provisioning as provisioning
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SANDBOX_GRANT_STORAGE_KEY,
)
from processual_api.services.evaluation_grants import EVALUATION_GRANTS_STORAGE_KEY


GRANT_ID = "eval_provisioning_test"
ADMIN_OWNER_ID = "platform-admin"
CLIENT_ID = "postman-eval-001"
EVALUATION_OWNER_ID = "postman-eval-owner"
BINDING_ID = "crm.customer.lookup"


def _admin() -> dict:
    return {
        "sub": ADMIN_OWNER_ID,
        "user_id": ADMIN_OWNER_ID,
        "client_id": ADMIN_OWNER_ID,
        "email": "platform-admin@example.test",
        "role": "security_admin",
        "session_type": "ui_admin",
    }


def _grant(*, status: str = "active", expires_at: datetime | None = None) -> dict:
    expiry = expires_at or (datetime.now(UTC) + timedelta(days=1))
    return {
        "grant_id": GRANT_ID,
        "status": status,
        "client_id": CLIENT_ID,
        "user_id": EVALUATION_OWNER_ID,
        "issued_to": "External evaluator",
        "purpose": "Bounded external CRM read evaluation",
        "allowed_task_ids": ["crm.customer_context"],
        "task_scope_ids": ["crm:read"],
        "allowed_endpoints": [
            {"method": "POST", "path": "/evaluation/runtime/task-execute"}
        ],
        "allowed_scopes": ["crm:read", "run:evaluation"],
        "max_requests": 100,
        "expires_at": expiry.isoformat(),
        "production_allowed": False,
    }


def _crm_binding() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id=BINDING_ID,
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


def _secret() -> SandboxSecretReference:
    return SandboxSecretReference(
        binding_id=BINDING_ID,
        provider_id="customer_vault",
        secret_reference="acme/crm/sandbox-reader",
    )


def _content() -> SandboxContentContract:
    return SandboxContentContract(
        binding_id=BINDING_ID,
        dataset_reference="customer_acme_crm_sandbox_v1",
        fixture_profile_reference="crm_customer_context_happy_path_v1",
        required_record_types=("customer",),
        acceptance_criteria_references=("crm_customer_context_read_v1",),
    )


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": (
                f"/settings/admin/evaluation-grants/{GRANT_ID}/"
                f"endpoint-bindings/{BINDING_ID}/sandbox-grant"
            ),
            "raw_path": b"/settings/admin/evaluation-grants/test/sandbox-grant",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 18000),
            "root_path": "",
        }
    )


def _patch_store(monkeypatch, tmp_path, grant: dict | None = None) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    settings_router._save_raw(
        ADMIN_OWNER_ID,
        {EVALUATION_GRANTS_STORAGE_KEY: [grant or _grant()]},
    )


async def _allow_platform_admin(_current_user: dict) -> None:
    return None


def _allow_admin(monkeypatch) -> None:
    monkeypatch.setattr(
        provisioning,
        "require_active_platform_admin",
        _allow_platform_admin,
    )


def test_evaluation_provisioning_routes_are_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }
    root = "/settings/admin/evaluation-grants/{grant_id}/endpoint-bindings/{binding_id}"
    assert root in paths
    assert f"{root}/request-mapping" in paths
    assert f"{root}/sandbox-secret-reference" in paths
    assert f"{root}/sandbox-content-contract" in paths
    assert f"{root}/sandbox-grant" in paths


def test_binding_is_saved_to_grant_user_store_not_admin_or_client_store(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_store(monkeypatch, tmp_path)
    _allow_admin(monkeypatch)

    result = asyncio.run(
        provisioning.save_evaluation_endpoint_binding(
            GRANT_ID,
            BINDING_ID,
            _crm_binding(),
            _admin(),
        )
    )

    assert result["status"] == "saved"
    assert result["evaluation_owner_id"] == EVALUATION_OWNER_ID
    owner_raw = settings_router._load_raw(EVALUATION_OWNER_ID)
    assert owner_raw[BINDING_STORAGE_KEY][0]["binding_id"] == BINDING_ID
    assert BINDING_STORAGE_KEY not in settings_router._load_raw(ADMIN_OWNER_ID)
    assert BINDING_STORAGE_KEY not in settings_router._load_raw(CLIENT_ID)


def test_binding_task_cannot_escape_evaluation_grant_authority(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_store(monkeypatch, tmp_path)
    _allow_admin(monkeypatch)
    body = _crm_binding().model_copy(update={"task_id": "billing.account_context"})

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            provisioning.save_evaluation_endpoint_binding(
                GRANT_ID,
                BINDING_ID,
                body,
                _admin(),
            )
        )

    assert exc_info.value.status_code == 403
    assert BINDING_STORAGE_KEY not in settings_router._load_raw(EVALUATION_OWNER_ID)


def test_mapping_secret_and_content_share_the_grant_owner_store(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_store(monkeypatch, tmp_path)
    _allow_admin(monkeypatch)
    asyncio.run(
        provisioning.save_evaluation_endpoint_binding(
            GRANT_ID,
            BINDING_ID,
            _crm_binding(),
            _admin(),
        )
    )

    mapping = EnterpriseEndpointRequestMappingSpec(binding_id=BINDING_ID)
    asyncio.run(
        provisioning.save_evaluation_endpoint_request_mapping(
            GRANT_ID,
            BINDING_ID,
            mapping,
            _admin(),
        )
    )
    secret_result = asyncio.run(
        provisioning.save_evaluation_sandbox_secret_reference(
            GRANT_ID,
            BINDING_ID,
            _secret(),
            _admin(),
        )
    )
    content_result = asyncio.run(
        provisioning.save_evaluation_sandbox_content_contract(
            GRANT_ID,
            BINDING_ID,
            _content(),
            _admin(),
        )
    )

    raw = settings_router._load_raw(EVALUATION_OWNER_ID)
    assert raw[REQUEST_MAPPING_STORAGE_KEY][0]["binding_id"] == BINDING_ID
    assert raw[SANDBOX_SECRET_REFERENCE_STORAGE_KEY][0]["binding_id"] == BINDING_ID
    assert raw[SANDBOX_CONTENT_STORAGE_KEY][0]["binding_id"] == BINDING_ID
    assert secret_result["secret_reference"]["value_included"] is False
    assert content_result["content_contract"]["raw_payloads_included"] is False


def test_sandbox_grant_keeps_supervisor_guard_and_same_owner_store(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_store(monkeypatch, tmp_path)
    _allow_admin(monkeypatch)
    asyncio.run(
        provisioning.save_evaluation_endpoint_binding(
            GRANT_ID,
            BINDING_ID,
            _crm_binding(),
            _admin(),
        )
    )

    guard_calls: list[str] = []

    def _approved_guard(request: Request) -> dict:
        guard_calls.append(request.url.path)
        return {"key_id": "supervisor-session-test"}

    monkeypatch.setattr(
        provisioning.binding_runtime,
        "_require_supervisor_approval_session",
        _approved_guard,
    )

    result = asyncio.run(
        provisioning.grant_evaluation_endpoint_sandbox_execution(
            GRANT_ID,
            BINDING_ID,
            provisioning.binding_runtime.EndpointSandboxGrantRequest(ttl_minutes=30),
            _request(),
            _admin(),
        )
    )

    assert guard_calls
    assert result["status"] == "sandbox_execution_granted"
    assert result["supervisor_session_key_id"] == "supervisor-session-test"
    owner_raw = settings_router._load_raw(EVALUATION_OWNER_ID)
    assert owner_raw[SANDBOX_GRANT_STORAGE_KEY][0]["binding_id"] == BINDING_ID
    assert SANDBOX_GRANT_STORAGE_KEY not in settings_router._load_raw(CLIENT_ID)


def test_inactive_evaluation_grant_cannot_provision(monkeypatch, tmp_path) -> None:
    expired = _grant(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    _patch_store(monkeypatch, tmp_path, expired)
    _allow_admin(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            provisioning.save_evaluation_endpoint_binding(
                GRANT_ID,
                BINDING_ID,
                _crm_binding(),
                _admin(),
            )
        )

    assert exc_info.value.status_code == 409
    assert "not active" in str(exc_info.value.detail).lower()
    assert BINDING_STORAGE_KEY not in settings_router._load_raw(EVALUATION_OWNER_ID)


def test_platform_admin_authority_is_required(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)

    async def _deny(_current_user: dict) -> None:
        raise HTTPException(status_code=403, detail="platform admin required")

    monkeypatch.setattr(provisioning, "require_active_platform_admin", _deny)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            provisioning.save_evaluation_endpoint_binding(
                GRANT_ID,
                BINDING_ID,
                _crm_binding(),
                _admin(),
            )
        )

    assert exc_info.value.status_code == 403
    assert BINDING_STORAGE_KEY not in settings_router._load_raw(EVALUATION_OWNER_ID)
