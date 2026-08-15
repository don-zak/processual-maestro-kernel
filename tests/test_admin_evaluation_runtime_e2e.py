from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_admin_evaluation_grants as grant_routes
from processual_api.services import api_key_store


def _admin() -> dict:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "client_id": "evaluation-owner",
        "role": "security_admin",
        "session_type": "ui_admin",
        "scopes": ["admin:api_keys:write"],
    }


def _request(method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
            "http_version": "1.1",
        }
    )


def _allow_super_admin_business_logic(monkeypatch) -> None:
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


def _create_grant() -> dict:
    return asyncio.run(
        grant_routes.create_evaluation_grant(
            body=grant_routes.EvaluationGrantCreate(
                client_id="runtime-e2e-client",
                user_id="runtime-e2e-user",
                issued_to="Assigned evaluation supervisor",
                purpose="Bounded real-runtime integration validation",
                allowed_task_ids=["crm.customer_context"],
                allowed_endpoints=[
                    grant_routes.EvaluationEndpointSelection(
                        method="GET",
                        path="/adapters/status",
                    )
                ],
                allowed_scopes=["read:adapters"],
                max_requests=5,
                expires_in_days=1,
            ),
            current_user=_admin(),
        )
    )


def _issue_key(grant_id: str) -> dict:
    return asyncio.run(
        grant_routes.issue_evaluation_key(
            grant_id=grant_id,
            body=grant_routes.EvaluationKeyIssue(
                label="Runtime lifecycle E2E key"
            ),
            current_user=_admin(),
        )
    )


def _authenticate(raw_key: str, method: str, path: str) -> dict:
    return asyncio.run(
        security.get_current_user(
            request=_request(method, path),
            bearer=None,
            api_key=raw_key,
            supervisor_session_key=None,
        )
    )


def test_evaluation_runtime_full_allowed_denied_revoke_sequence(
    monkeypatch,
    tmp_path,
) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    _allow_super_admin_business_logic(monkeypatch)

    grant = _create_grant()["grant"]
    issued = _issue_key(grant["grant_id"])
    raw_key = issued["api_key"]

    allowed_identity = _authenticate(
        raw_key,
        "GET",
        "/adapters/status",
    )
    assert allowed_identity["evaluation_grant_id"] == grant["grant_id"]
    assert allowed_identity["execution_mode"] == "evaluation_runtime"
    assert allowed_identity["real_runtime_execution"] is True
    assert allowed_identity["subscription_required"] is False

    with pytest.raises(HTTPException) as unselected:
        _authenticate(raw_key, "GET", "/health/ready")
    assert unselected.value.status_code == 403
    assert (
        str(unselected.value.detail)
        == "Evaluation grant does not allow this runtime endpoint."
    )

    with pytest.raises(HTTPException) as control_plane:
        _authenticate(
            raw_key,
            "GET",
            "/settings/admin/evaluation-grants",
        )
    assert control_plane.value.status_code == 403

    revoked = asyncio.run(
        grant_routes.revoke_evaluation_grant(
            grant_id=grant["grant_id"],
            current_user=_admin(),
        )
    )
    assert revoked["status"] == "revoked"
    assert revoked["revoked_key_count"] == 1

    with pytest.raises(HTTPException) as after_revoke:
        _authenticate(raw_key, "GET", "/adapters/status")
    assert after_revoke.value.status_code == 401
    assert "invalid api key" in str(after_revoke.value.detail).lower()
