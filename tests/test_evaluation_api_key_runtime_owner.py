from __future__ import annotations

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
