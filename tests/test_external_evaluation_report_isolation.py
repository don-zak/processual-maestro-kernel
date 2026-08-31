from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.routers import settings_admin_evaluation_grants as grant_routes


def _admin() -> dict[str, object]:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "client_id": "evaluation-owner",
        "session_type": "identity_user",
        "session_id": "evaluation-session",
        "scopes": ["evaluation"],
    }


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


@pytest.fixture(autouse=True)
def _allow_platform_admin_authority(monkeypatch) -> None:
    async def allow(current_user: dict, request: Request | None = None) -> dict:
        return current_user

    monkeypatch.setattr(grant_routes, "require_active_platform_admin", allow)


def test_external_evaluation_catalog_excludes_unscoped_governance_reports() -> None:
    payload = asyncio.run(
        grant_routes.evaluation_access_catalog(
            request=_request(
                "GET",
                "/settings/admin/evaluation-grants/access-catalog",
            ),
            current_user=_admin(),
        )
    )

    endpoints = {
        (str(item["method"]), str(item["path"]))
        for item in payload["endpoints"]
    }
    assert payload["production_allowed"] is False
    assert len(endpoints) == 7
    assert ("GET", "/cgt/govern/reports") not in endpoints
    assert ("POST", "/evaluation/runtime/task-execute") in endpoints


def test_external_evaluation_grant_rejects_shared_governance_reports() -> None:
    body = grant_routes.EvaluationGrantCreate(
        client_id="external-eval-client",
        issued_to="External Evaluation Team",
        purpose="Controlled product qualification without shared history access",
        allowed_task_ids=["crm.customer_context"],
        allowed_endpoints=[
            {"method": "GET", "path": "/cgt/govern/reports"},
        ],
        allowed_scopes=["read:reports"],
        max_requests=10,
        expires_in_days=7,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            grant_routes.create_evaluation_grant(
                body=body,
                request=_request("POST", "/settings/admin/evaluation-grants"),
                current_user=_admin(),
            )
        )

    assert exc.value.status_code == 422
    detail = str(exc.value.detail).lower()
    assert "not eligible for evaluation access" in detail
    assert "get /cgt/govern/reports" in detail
