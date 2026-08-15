from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.integrations.api_key_access_policy import get_api_key_access_policy
from processual_api.routers import cgt_governor, evaluation_runtime


def _evaluation_user(*, allowed_tasks: list[str]) -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "evaluation_grant_id": "eval_test",
        "api_key_id": "evalkey_test",
        "scopes": ["run:evaluation"],
        "allowed_task_ids": allowed_tasks,
    }


def _binding(task_id: str = "crm.customer_context") -> SimpleNamespace:
    return SimpleNamespace(
        binding_id="binding-crm-context",
        task_id=task_id,
        adapter_contract_id="crm",
        method="GET",
    )


def test_runtime_task_bridge_is_canonical_grantable_surface() -> None:
    policy = get_api_key_access_policy(
        "POST",
        "/evaluation/runtime/task-execute",
    )
    assert policy is not None
    assert policy.task_id == "platform.evaluation.task_execute"
    assert policy.required_scopes == ("run:evaluation",)
    assert policy.production_allowed is False

    matching = [
        route
        for route in cgt_governor.router.routes
        if getattr(route, "path", "") == "/evaluation/runtime/task-execute"
        and "POST" in (getattr(route, "methods", set()) or set())
    ]
    assert len(matching) == 1


def test_ungranted_task_is_denied_before_network_execution(monkeypatch) -> None:
    network_called = False

    monkeypatch.setattr(
        evaluation_runtime.settings_router,
        "_load_raw",
        lambda _owner: {},
    )
    monkeypatch.setattr(
        evaluation_runtime.binding_runtime,
        "_find_binding",
        lambda _raw, _binding_id: _binding(),
    )

    async def _network_must_not_run(*args, **kwargs):
        nonlocal network_called
        network_called = True
        raise AssertionError("network execution must not run for an ungranted task")

    monkeypatch.setattr(
        evaluation_runtime,
        "execute_sandbox_binding",
        _network_must_not_run,
    )

    body = evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
        task_id="crm.customer_context",
        binding_id="binding-crm-context",
        task_input={"customer_id": "customer-1"},
    )

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            evaluation_runtime.execute_evaluation_runtime_task(
                body=body,
                current_user=_evaluation_user(
                    allowed_tasks=["support.response_draft"]
                ),
            )
        )

    assert exc.value.status_code == 403
    assert "does not allow this canonical task" in str(exc.value.detail)
    assert network_called is False


def test_binding_task_mismatch_is_denied_before_network_execution(monkeypatch) -> None:
    network_called = False

    monkeypatch.setattr(
        evaluation_runtime.settings_router,
        "_load_raw",
        lambda _owner: {},
    )
    monkeypatch.setattr(
        evaluation_runtime.binding_runtime,
        "_find_binding",
        lambda _raw, _binding_id: _binding("crm.customer_context"),
    )

    async def _network_must_not_run(*args, **kwargs):
        nonlocal network_called
        network_called = True
        raise AssertionError("network execution must not run for a task mismatch")

    monkeypatch.setattr(
        evaluation_runtime,
        "execute_sandbox_binding",
        _network_must_not_run,
    )

    body = evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
        task_id="support.response_draft",
        binding_id="binding-crm-context",
        task_input={},
    )

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            evaluation_runtime.execute_evaluation_runtime_task(
                body=body,
                current_user=_evaluation_user(
                    allowed_tasks=[
                        "crm.customer_context",
                        "support.response_draft",
                    ]
                ),
            )
        )

    assert exc.value.status_code == 403
    assert "does not match" in str(exc.value.detail)
    assert network_called is False


def test_allowed_read_task_executes_and_records_truthful_completion(
    monkeypatch,
) -> None:
    raw: dict = {}
    saved: dict = {}
    network_calls = 0

    monkeypatch.setattr(
        evaluation_runtime.settings_router,
        "_load_raw",
        lambda _owner: raw,
    )
    monkeypatch.setattr(
        evaluation_runtime.settings_router,
        "_save_raw",
        lambda owner, payload: saved.update({"owner": owner, "payload": payload}),
    )
    monkeypatch.setattr(
        evaluation_runtime.binding_runtime,
        "_find_binding",
        lambda _raw, _binding_id: _binding(),
    )
    monkeypatch.setattr(
        evaluation_runtime.binding_runtime,
        "_find_request_mapping",
        lambda _raw, _binding_id: None,
    )
    monkeypatch.setattr(
        evaluation_runtime.sandbox_runtime,
        "_content_contract",
        lambda _raw, _binding_id: SimpleNamespace(
            dataset_reference="dataset-ref",
            fixture_profile_reference="fixture-ref",
        ),
    )
    monkeypatch.setattr(
        evaluation_runtime.sandbox_runtime,
        "_secret_reference",
        lambda _raw, _binding_id: SimpleNamespace(
            binding_id="binding-crm-context",
            provider_id="provider-ref",
            secret_reference="secret-ref",
        ),
    )
    monkeypatch.setattr(
        evaluation_runtime,
        "resolve_active_sandbox_execution_grant",
        lambda _raw, *, binding_id, task_id: {
            "grant_id": "segrant-test",
            "binding_id": binding_id,
            "task_id": task_id,
            "approved_operation_classes": ["read"],
        },
    )

    class _Transport:
        def __init__(self) -> None:
            self.last_verified_peer = None

    monkeypatch.setattr(
        evaluation_runtime,
        "VerifiedPeerSandboxTransport",
        _Transport,
    )

    async def _execute(
        spec,
        *,
        task_input,
        request_body,
        approved_operation_classes,
        approval_reference,
        credential_resolver,
        transport,
    ):
        nonlocal network_calls
        del task_input, request_body, credential_resolver
        network_calls += 1
        assert spec.task_id == "crm.customer_context"
        assert approved_operation_classes == {"read"}
        assert approval_reference == "segrant-test"
        transport.last_verified_peer = "203.0.113.10"
        return {
            "execution_id": "exec-test",
            "task_id": "crm.customer_context",
            "operation_class": "read",
            "output_slot": "crm_context",
            "canonical_input": {"customer_id": "customer-1"},
            "http_status": 200,
            "network_request_executed": True,
            "mapping_valid": True,
            "ready_for_task_consumption": True,
            "response_sha256": "response-hash",
            "task_injection_sha256": "injection-hash",
            "evidence_sha256": "evidence-hash",
            "completed_at": "2026-08-15T17:30:00+00:00",
        }

    monkeypatch.setattr(
        evaluation_runtime,
        "execute_sandbox_binding",
        _execute,
    )

    import asyncio

    result = asyncio.run(
        evaluation_runtime.execute_evaluation_runtime_task(
            body=evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
                task_id="crm.customer_context",
                binding_id="binding-crm-context",
                task_input={"customer_id": "customer-1"},
            ),
            current_user=_evaluation_user(
                allowed_tasks=["crm.customer_context"]
            ),
        )
    )

    assert network_calls == 1
    assert result["evaluation_runtime"] is True
    assert result["task_authority_enforced"] is True
    assert result["evaluation_stage"] == "canonical_task_completed"
    assert result["network_request_executed"] is True
    assert result["ready_for_task_consumption"] is True
    assert result["maestro_task_completed"] is True
    assert result["completion_stage"] == "canonical_read_task_completed"
    assert result["completion_sha256"]
    assert result["next_readiness_stage"] == "outcome_quality_validation"
    assert saved["owner"] == "evaluation-owner"

    evidence = saved["payload"][
        evaluation_runtime.EVALUATION_TASK_EVIDENCE_STORAGE_KEY
    ][0]
    assert evidence["task_id"] == "crm.customer_context"
    assert evidence["network_request_executed"] is True
    assert evidence["maestro_task_completed"] is True
    assert evidence["completion_stage"] == "canonical_read_task_completed"
    assert evidence["task_completion_sha256"]
    assert "canonical_input" not in evidence


def test_draft_task_remains_incomplete_without_dedicated_consumer() -> None:
    completion = evaluation_runtime._completion_from_external_result(
        task_id="support.response_draft",
        binding_id="binding-support-draft",
        result={
            "output_slot": "support_response_draft",
            "canonical_input": {
                "ticket_id": "ticket-1",
                "issue_context": "customer cannot authenticate",
            },
        },
    )

    assert completion["maestro_task_completed"] is False
    assert completion["completion_stage"] == "downstream_consumer_required"
    assert completion["dedicated_downstream_consumer_required"] is True


def test_non_evaluation_api_key_cannot_use_task_bridge() -> None:
    user = _evaluation_user(allowed_tasks=["crm.customer_context"])
    user["entitlement_source"] = "subscription"

    body = evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
        task_id="crm.customer_context",
        binding_id="binding-crm-context",
        task_input={},
    )

    with pytest.raises(HTTPException) as exc:
        import asyncio

        asyncio.run(
            evaluation_runtime.execute_evaluation_runtime_task(
                body=body,
                current_user=user,
            )
        )

    assert exc.value.status_code == 403
    assert "Evaluation Runtime credential required" in str(exc.value.detail)
