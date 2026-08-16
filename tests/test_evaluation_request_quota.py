from __future__ import annotations

import asyncio

from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.services import api_key_store


def _admin() -> dict:
    return {
        "sub": "evaluation-quota-owner",
        "user_id": "evaluation-quota-owner",
        "client_id": "evaluation-quota-owner",
        "role": "security_admin",
        "session_type": "ui_admin",
        "scopes": ["admin:api_keys:write"],
    }


def _allow_super_admin(monkeypatch) -> None:
    async def _allow(_current_user: dict) -> None:
        return None

    monkeypatch.setattr(
        grant_routes,
        "require_active_platform_admin",
        _allow,
    )


def _patch_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)


def test_evaluation_request_limit_is_independent_and_fail_closed(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin(monkeypatch)

    created = asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="quota-eval-client",
                user_id="quota-eval-user",
                issued_to="Quota Evaluation Supervisor",
                purpose="Bounded real-runtime evaluation request quota proof",
                allowed_task_ids=["crm.customer_context"],
                allowed_endpoints=[
                    grant_routes.EvaluationEndpointSelection(
                        method="GET",
                        path="/adapters/status",
                    )
                ],
                allowed_scopes=["read:adapters"],
                max_requests=2,
                expires_in_days=1,
            ),
            current_user=_admin(),
        )
    )
    grant_id = created["grant"]["grant_id"]
    issued = asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=grant_id,
            body=grant_routes.EvaluationKeyIssue(label="Quota proof"),
            current_user=_admin(),
        )
    )
    raw_key = issued["api_key"]

    first = api_key_store.verify_dynamic_api_key(raw_key)
    second = api_key_store.verify_dynamic_api_key(raw_key)
    third = api_key_store.verify_dynamic_api_key(raw_key)

    assert first is not None
    assert first["evaluation_request_limit"] == 2
    assert first["evaluation_request_used"] == 1
    assert first["evaluation_request_remaining"] == 1

    assert second is not None
    assert second["evaluation_request_limit"] == 2
    assert second["evaluation_request_used"] == 2
    assert second["evaluation_request_remaining"] == 0

    assert third is None

    raw = settings_router._load_raw("evaluation-quota-owner")
    stored = raw["api_keys"][0]
    assert stored["evaluation_request_limit"] == 2
    assert stored["evaluation_request_used"] == 2
    assert stored["evaluation_request_state"] == "evaluation_request_quota_exhausted"
    assert stored["evaluation_request_last_rejected_at"]
    assert stored["quota_used"] == 0
