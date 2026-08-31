from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.routers import settings_enterprise_evaluation_sandbox_guard as guard
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as runtime


def _evaluation_identity(**overrides):
    identity = {
        "sub": "client-1",
        "user_id": "client-1",
        "client_id": "client-1",
        "evaluation_grant_id": "eval_1",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "task_authority_source": "integration_task_catalog",
        "allowed_task_ids": ["crm.customer_context"],
        "task_scope_ids": ["crm:read"],
    }
    identity.update(overrides)
    return identity


def test_evaluation_identity_requires_explicit_admin_grant_authority():
    assert guard._is_evaluation_identity(_evaluation_identity()) is True
    assert guard._is_evaluation_identity(
        _evaluation_identity(subscription_required=True)
    ) is False
    assert guard._is_evaluation_identity(
        _evaluation_identity(entitlement_source="subscription")
    ) is False
    assert guard._is_evaluation_identity(
        _evaluation_identity(task_authority_source="legacy")
    ) is False


def test_task_outside_evaluation_allowlist_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        guard._require_evaluation_task_authority(
            _evaluation_identity(),
            "support.ticket_history",
        )

    assert exc_info.value.status_code == 403
    assert "not authorized" in str(exc_info.value.detail).lower()


def test_missing_canonical_task_scope_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        guard._require_evaluation_task_authority(
            _evaluation_identity(task_scope_ids=[]),
            "crm.customer_context",
        )

    assert exc_info.value.status_code == 403
    assert "scope authority" in str(exc_info.value.detail).lower()


def test_canonical_allowed_task_and_scope_are_accepted():
    guard._require_evaluation_task_authority(
        _evaluation_identity(),
        "crm.customer_context",
    )


@pytest.mark.asyncio
async def test_non_evaluation_identity_keeps_subscription_runtime_path(monkeypatch):
    captured = {}

    async def fake_original(binding_id, body, current_user):
        captured["binding_id"] = binding_id
        captured["current_user"] = current_user
        return {"source": "subscription"}

    monkeypatch.setattr(
        runtime,
        "execute_enterprise_endpoint_sandbox_proof",
        fake_original,
    )

    identity = {
        "user_id": "client-1",
        "client_id": "client-1",
        "subscription_required": True,
    }
    body = runtime.EndpointSandboxExecuteRequest(task_input={})
    result = await guard.guarded_execute_enterprise_endpoint_sandbox_proof(
        "binding-1",
        body,
        identity,
    )

    assert result == {"source": "subscription"}
    assert captured == {
        "binding_id": "binding-1",
        "current_user": identity,
    }


@pytest.mark.asyncio
async def test_evaluation_execution_requires_task_allowlist_and_supervisor_grant(
    monkeypatch,
):
    raw = {}
    saved = {}
    spec = SimpleNamespace(
        binding_id="binding-1",
        task_id="crm.customer_context",
        method="GET",
    )

    monkeypatch.setattr(guard.settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(runtime, "_find_binding", lambda data, binding_id: spec)
    monkeypatch.setattr(runtime, "_find_request_mapping", lambda data, binding_id: None)
    monkeypatch.setattr(
        runtime,
        "resolve_active_sandbox_execution_grant",
        lambda data, binding_id, task_id: {
            "grant_id": "sandbox-grant-1",
            "approved_operation_classes": ["read"],
        },
    )

    async def fake_execute(
        binding,
        *,
        task_input,
        request_body,
        approved_operation_classes,
        approval_reference,
    ):
        assert binding is spec
        assert task_input == {"customer_id": "c-1"}
        assert request_body is None
        assert approved_operation_classes == {"read"}
        assert approval_reference == "sandbox-grant-1"
        return {
            "task_id": binding.task_id,
            "output_slot": "crm_context",
            "canonical_input": {"customer_id": "c-1"},
            "production_allowed": False,
        }

    monkeypatch.setattr(runtime, "execute_sandbox_binding", fake_execute)
    monkeypatch.setattr(runtime, "_safe_evidence", lambda data: [])
    monkeypatch.setattr(
        guard.settings_module,
        "_save_raw",
        lambda user_id, data: saved.update({"user_id": user_id, "data": data}),
    )

    body = runtime.EndpointSandboxExecuteRequest(
        task_input={"customer_id": "c-1"}
    )
    result = await guard.guarded_execute_enterprise_endpoint_sandbox_proof(
        "binding-1",
        body,
        _evaluation_identity(),
    )

    assert result["task_id"] == "crm.customer_context"
    assert result["production_allowed"] is False
    evidence = saved["data"][runtime.SANDBOX_EVIDENCE_STORAGE_KEY]
    assert evidence == [
        {
            "task_id": "crm.customer_context",
            "output_slot": "crm_context",
            "production_allowed": False,
            "canonical_output_slot": "crm_context",
        }
    ]


def test_sandbox_execute_route_is_registered_once():
    matches = [
        route
        for route in runtime.settings_module.router.routes
        if getattr(route, "path", "") == guard._SANDBOX_EXECUTE_PATH
        and "POST" in (getattr(route, "methods", set()) or set())
    ]
    assert len(matches) == 1
