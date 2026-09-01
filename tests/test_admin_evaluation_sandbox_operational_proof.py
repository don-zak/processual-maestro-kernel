from __future__ import annotations

import asyncio
from types import SimpleNamespace

from starlette.requests import Request

from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_binding_provisioning as routes
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as binding_runtime


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "session_type": "identity_user",
        "session_id": "evaluation-session",
    }


def _request() -> Request:
    path = "/settings/admin/evaluation-grants/bindings/evaluation.crm.customer/sandbox-operational-execute"
    return Request(
        {
            "type": "http",
            "method": "POST",
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


def test_evaluation_live_proof_is_subscription_independent_and_persists_safe_evidence(
    monkeypatch,
) -> None:
    raw: dict = {}
    spec = SimpleNamespace(
        binding_id="evaluation.crm.customer",
        task_id="crm.customer_context",
        adapter_contract_id="crm",
        credential_profile_id="enterprise_core_api_reference",
        method="GET",
    )
    content = SimpleNamespace(
        dataset_reference="evaluation_crm_dataset_v1",
        fixture_profile_reference="evaluation_crm_fixture_v1",
    )
    secret_reference = SimpleNamespace(binding_id=spec.binding_id)

    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    class Transport:
        def __init__(self) -> None:
            self.last_verified_peer = "203.0.113.10"

    async def execute(*_args, **_kwargs):
        return {
            "binding_id": spec.binding_id,
            "task_id": spec.task_id,
            "output_slot": "crm_context",
            "network_request_executed": True,
            "mapping_valid": True,
            "ready_for_task_consumption": True,
            "canonical_input": {"customer_id": "123"},
            "production_allowed": False,
            "runtime_connector_approved": False,
        }

    saved: dict = {}

    monkeypatch.setattr(routes, "require_active_platform_admin", allow)
    monkeypatch.setattr(settings_router, "_load_raw", lambda _owner_id: raw)
    monkeypatch.setattr(settings_router, "_save_raw", lambda _owner_id, value: saved.update(value))
    monkeypatch.setattr(binding_runtime, "_find_binding", lambda _raw, _binding_id: spec)
    monkeypatch.setattr(binding_runtime, "_find_request_mapping", lambda _raw, _binding_id: None)
    monkeypatch.setattr(routes.sandbox_runtime, "_content_contract", lambda _raw, _binding_id: content)
    monkeypatch.setattr(routes.sandbox_runtime, "_secret_reference", lambda _raw, _binding_id: secret_reference)
    monkeypatch.setattr(routes.sandbox_runtime, "_provisioning_sha256", lambda **_kwargs: "proof-sha")
    monkeypatch.setattr(
        routes,
        "resolve_active_sandbox_execution_grant",
        lambda _raw, *, binding_id, task_id: {
            "grant_id": "segrant-eval-001",
            "approved_operation_classes": ["read"],
        },
    )
    monkeypatch.setattr(routes, "ReferenceSandboxCredentialResolver", lambda _reference: object())
    monkeypatch.setattr(routes, "VerifiedPeerSandboxTransport", Transport)
    monkeypatch.setattr(routes, "execute_sandbox_binding", execute)

    result = asyncio.run(
        routes.execute_evaluation_sandbox_operational_proof(
            binding_id=spec.binding_id,
            body=binding_runtime.EndpointSandboxExecuteRequest(
                task_input={"customer_id": "123"}
            ),
            request=_request(),
            current_user=_admin(),
        )
    )

    assert result["operational_proof"] is True
    assert result["peer_address_verified"] is True
    assert result["selection_authority"] == "admin_evaluation_grant"
    assert result["subscription_required"] is False
    assert result["registration_required"] is False
    assert result["commercial_quota_required"] is False
    assert result["production_allowed"] is False
    assert result["runtime_connector_approved"] is False
    assert result["raw_secret_visible"] is False
    assert result["raw_payload_visible"] is False

    evidence = saved[binding_runtime.SANDBOX_EVIDENCE_STORAGE_KEY][-1]
    assert evidence["provisioning_sha256"] == "proof-sha"
    assert evidence["canonical_output_slot"] == "crm_context"
    assert "canonical_input" not in evidence
