from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Request

from processual_api.auth import evaluation_access_extension
from processual_api.services import api_key_store


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
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


def _identity() -> dict:
    return {
        "sub": "owner-user",
        "user_id": "owner-user",
        "client_id": "external-evaluator",
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "evaluation_grant_id": "eval_contract",
        "subscription_required": False,
    }


def _stored_grant() -> dict:
    return {
        "grant_id": "eval_contract",
        "status": "active",
        "client_id": "external-evaluator",
        "allowed_endpoints": [{"method": "GET", "path": "/health/live"}],
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_scopes": ["read:health"],
        "max_requests": 25,
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "production_allowed": False,
    }


@pytest.mark.asyncio
async def test_persisted_endpoint_envelope_is_applied_before_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api_key_store, "_DATA_DIR", tmp_path)
    (tmp_path / "settings_owner-user.json").write_text(
        json.dumps({"evaluation_grants_v1": [_stored_grant()]}),
        encoding="utf-8",
    )

    identity = await evaluation_access_extension.get_current_evaluation_guarded_user(
        _request("GET", "/health/live"),
        _identity(),
    )
    assert identity["evaluation_access"] is True
    assert identity["execution_mode"] == "evaluation_runtime"
    assert identity["subscription_required"] is False
    assert identity["commercial_quota_required"] is False

    with pytest.raises(HTTPException) as exc_info:
        await evaluation_access_extension.get_current_evaluation_guarded_user(
            _request("GET", "/settings"),
            _identity(),
        )
    assert exc_info.value.status_code == 403
