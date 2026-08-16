from __future__ import annotations

import asyncio

from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.services import api_key_store


def _governed_key() -> dict:
    return {
        "id": "evalkey_test",
        "user_id": "postman-eval-owner",
        "client_id": "postman-eval-001",
        "role": "client",
        "scopes": ["crm:read", "run:evaluation"],
        "category": "pilot_client",
        "evaluation_grant_id": "eval_test",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "production_allowed": False,
        "allowed_endpoints": [
            {"method": "POST", "path": "/evaluation/runtime/task-execute"}
        ],
        "allowed_task_ids": ["crm.customer_context"],
        "task_scope_ids": ["crm:read"],
        "quota_limit": 100,
        "evaluation_request_used": 1,
    }


def test_governed_evaluation_identity_uses_key_user_not_storage_owner() -> None:
    identity = api_key_store._public_identity(
        "platform-admin-storage-owner",
        {},
        _governed_key(),
    )

    assert identity["sub"] == "postman-eval-owner"
    assert identity["user_id"] == "postman-eval-owner"
    assert identity["client_id"] == "postman-eval-001"
    assert identity["evaluation_grant_id"] == "eval_test"
    assert identity["execution_mode"] == "evaluation_runtime"


def test_non_evaluation_identity_keeps_storage_owner_behavior() -> None:
    key = {
        "id": "normal_key",
        "user_id": "ignored-for-legacy-key",
        "client_id": "client-a",
        "role": "client",
        "scopes": ["read:health"],
    }

    identity = api_key_store._public_identity(
        "settings-file-owner",
        {},
        key,
    )

    assert identity["sub"] == "settings-file-owner"
    assert identity["user_id"] == "settings-file-owner"
    assert identity["client_id"] == "client-a"


def test_issued_evaluation_key_authenticates_as_grant_user(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)

    async def _allow(_current_user: dict) -> None:
        return None

    monkeypatch.setattr(
        grant_routes,
        "require_active_platform_admin",
        _allow,
    )
    admin = {
        "sub": "platform-admin-storage-owner",
        "user_id": "platform-admin-storage-owner",
        "client_id": "platform-admin-storage-owner",
        "role": "security_admin",
        "session_type": "ui_admin",
    }
    created = asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="postman-eval-001",
                user_id="postman-eval-owner",
                issued_to="External evaluator",
                purpose="Bounded external CRM read evaluation",
                allowed_task_ids=["crm.customer_context"],
                allowed_endpoints=[
                    grant_routes.EvaluationEndpointSelection(
                        method="POST",
                        path="/evaluation/runtime/task-execute",
                    )
                ],
                allowed_scopes=["crm:read", "run:evaluation"],
                max_requests=100,
                expires_in_days=14,
            ),
            current_user=admin,
        )
    )
    issued = asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=created["grant"]["grant_id"],
            body=grant_routes.EvaluationKeyIssue(label="Evaluation key"),
            current_user=admin,
        )
    )

    identity = api_key_store.verify_dynamic_api_key(issued["api_key"])

    assert identity is not None
    assert identity["sub"] == "postman-eval-owner"
    assert identity["user_id"] == "postman-eval-owner"
    assert identity["client_id"] == "postman-eval-001"
    assert identity["evaluation_grant_id"] == created["grant"]["grant_id"]
    admin_raw = settings_router._load_raw("platform-admin-storage-owner")
    assert admin_raw["api_keys"][0]["user_id"] == "postman-eval-owner"
