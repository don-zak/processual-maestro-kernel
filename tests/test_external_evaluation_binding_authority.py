from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from processual_api.routers import evaluation_runtime
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from processual_api.services import api_key_store
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_binding_allowed,
    key_evaluation_grant_state,
)


def _runtime_grant(*, binding_id: str = "binding_eval_a") -> dict:
    return {
        "grant_id": "eval_binding_a",
        "status": "active",
        "client_id": "client-a",
        "allowed_scopes": ["run:evaluation"],
        "allowed_endpoints": [
            {"method": "POST", "path": "/evaluation/runtime/task-execute"},
        ],
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": [binding_id],
        "max_requests": 20,
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "execution_mode": EVALUATION_EXECUTION_MODE,
        "real_runtime_execution": True,
        "production_allowed": False,
    }


def _evaluation_identity(*, binding_id: str = "binding_eval_a") -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "client_id": "client-a",
        "auth_method": "api_key",
        "session_type": "api_key",
        "api_key_id": "evalkey_a",
        "entitlement_source": "admin_evaluation_grant",
        "evaluation_grant_id": "eval_binding_a",
        "subscription_required": False,
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": [binding_id],
        "scopes": ["run:evaluation"],
    }


def test_binding_authority_is_fail_closed_across_evaluation_grants() -> None:
    identity = _evaluation_identity(binding_id="binding_eval_a")

    assert evaluation_binding_allowed(identity, "binding_eval_a") is True
    assert evaluation_binding_allowed(identity, "binding_eval_b") is False


def test_tampered_key_binding_expansion_is_rejected_by_grant_state() -> None:
    grant = _runtime_grant(binding_id="binding_eval_a")
    raw = {EVALUATION_GRANTS_STORAGE_KEY: [grant]}
    key = {
        "category": "pilot_client",
        "client_id": "client-a",
        "evaluation_grant_id": "eval_binding_a",
        "entitlement_source": "admin_evaluation_grant",
        "scopes": ["run:evaluation"],
        "allowed_endpoints": list(grant["allowed_endpoints"]),
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": ["binding_eval_a", "binding_eval_b"],
        "quota_limit": 20,
    }

    allowed, state = key_evaluation_grant_state(raw, key)

    assert allowed is False
    assert state == "evaluation_grant_binding_mismatch"


def test_public_identity_projects_binding_authority_from_canonical_grant() -> None:
    grant = _runtime_grant(binding_id="binding_eval_a")
    raw = {EVALUATION_GRANTS_STORAGE_KEY: [grant]}
    key = {
        "id": "evalkey_a",
        "client_id": "client-a",
        "role": "client",
        "scopes": ["run:evaluation"],
        "evaluation_grant_id": "eval_binding_a",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": ["binding_eval_b"],
    }

    identity = api_key_store._public_identity("evaluation-owner", raw, key)

    assert identity["allowed_binding_ids"] == ["binding_eval_a"]
    assert identity["allowed_endpoints"] == grant["allowed_endpoints"]


def test_runtime_rejects_ungranted_binding_before_binding_lookup(monkeypatch) -> None:
    grant = _runtime_grant(binding_id="binding_eval_a")
    raw = {EVALUATION_GRANTS_STORAGE_KEY: [grant]}

    async def load_shared_authority(_owner_id: str) -> dict:
        return raw

    monkeypatch.setattr(
        evaluation_runtime,
        "load_evaluation_authority_state",
        load_shared_authority,
    )

    lookup_called = False

    def forbidden_lookup(_raw, _binding_id):
        nonlocal lookup_called
        lookup_called = True
        raise AssertionError("binding lookup must not run before evaluation authority")

    monkeypatch.setattr(binding_runtime, "_find_binding", forbidden_lookup)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            evaluation_runtime.execute_evaluation_runtime_task(
                body=evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
                    task_id="crm.customer_context",
                    binding_id="binding_eval_b",
                    idempotency_key="binding-reject-001",
                    task_input={},
                ),
                current_user=_evaluation_identity(binding_id="binding_eval_a"),
            )
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Evaluation grant does not allow this prepared binding."
    assert lookup_called is False


def test_admin_runtime_grant_requires_prepared_binding() -> None:
    with pytest.raises(HTTPException) as exc:
        grant_routes._binding_selection(
            {},
            [],
            task_ids=["crm.customer_context"],
            endpoints=[
                {"method": "POST", "path": "/evaluation/runtime/task-execute"},
            ],
        )

    assert exc.value.status_code == 422
    assert "requires at least one prepared binding" in str(exc.value.detail)
