from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

import processual_api.middleware.usage_log as usage_log_module
import processual_api.services.quota_store as quota_store
import processual_api.services.usage_log_store as usage_log_store
from processual_api.auth.security import require_quota
from processual_api.middleware.usage_log import UsageLogMiddleware


def _request(method: str, path: str) -> Request:
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    })


def _api_key_user() -> dict[str, Any]:
    return {
        "sub": "rejected-user",
        "user_id": "rejected-user",
        "client_id": "rejected-client",
        "role": "service",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "api_key_id": "key_rejected",
        "api_key_prefix": "pmk_rej",
        "scopes": ["run:govern"],
    }


def test_require_quota_preserves_rejection_metadata_on_request_state(
    monkeypatch,
):
    def fake_consume_quota(
        current_user: dict[str, Any],
        *,
        method: str,
        endpoint: str,
        quota_scope: str = "evaluation",
        amount: int = 1,
    ) -> dict[str, Any]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "quota_scope": quota_scope,
                "plan_id": "business",
                "quota_limit": 100,
                "quota_used": 98,
                "quota_requested": amount,
                "quota_remaining": 2,
            },
        )

    monkeypatch.setattr(quota_store, "consume_quota", fake_consume_quota)

    request = _request("POST", "/cgt/govern/auto-repair")
    dependency = require_quota("evaluation")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dependency(request, _api_key_user()))

    assert exc.value.status_code == 429
    assert request.state.pricing_units_charged == 5

    rejected_user = request.state.current_user
    assert rejected_user["quota_rejected"] is True
    assert rejected_user["quota"] == {
        "scope": "evaluation",
        "plan_id": "business",
        "limit": 100,
        "used": 98,
        "requested": 5,
        "remaining": 2,
        "rejected": True,
    }


def test_usage_log_middleware_attaches_rejection_quota_flag(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(usage_log_module, "append_usage_log", captured.append)

    request = _request("POST", "/cgt/govern/auto-repair")
    request.state.current_user = {
        **_api_key_user(),
        "quota_rejected": True,
        "quota": {
            "scope": "evaluation",
            "plan_id": "business",
            "limit": 100,
            "used": 98,
            "requested": 5,
            "remaining": 2,
            "rejected": True,
        },
    }

    async def call_next(_request: Request) -> Response:
        return Response(
            status_code=429,
            headers={"X-Request-ID": "req-rejected-001"},
        )

    middleware = UsageLogMiddleware(app=lambda scope, receive, send: None)
    asyncio.run(middleware.dispatch(request, call_next))

    assert len(captured) == 1
    record = captured[0]

    assert record["status_code"] == 429
    assert record["endpoint"] == "/cgt/govern/auto-repair"
    assert record["units_charged"] == 5
    assert record["quota_scope"] == "evaluation"
    assert record["plan_id"] == "business"
    assert record["quota_limit"] == 100
    assert record["quota_used"] == 98
    assert record["quota_requested"] == 5
    assert record["quota_remaining"] == 2
    assert record["quota_before"] == 93
    assert record["quota_after"] == 98
    assert record["quota_rejected"] is True


def test_usage_log_store_persists_rejection_audit_metadata(
    tmp_path,
    monkeypatch,
):
    usage_log_path = tmp_path / "usage_logs.jsonl"

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    usage_log_store.append_usage_log({
        "request_id": "req-rejected-store-001",
        "client_id": "rejected-client",
        "user_id": "rejected-user",
        "api_key_id": "key_rejected",
        "api_key_prefix": "pmk_rej",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "method": "POST",
        "endpoint": "/cgt/govern/auto-repair",
        "status_code": 429,
        "latency_ms": 1.25,
        "role": "service",
        "units_charged": 5,
        "quota_scope": "evaluation",
        "quota_limit": 100,
        "quota_used": 98,
        "quota_requested": 5,
        "quota_remaining": 2,
        "quota_before": 93,
        "quota_after": 98,
        "plan_id": "business",
        "quota_rejected": True,
    })

    record = json.loads(usage_log_path.read_text(encoding="utf-8").splitlines()[0])

    assert record["status_code"] == 429
    assert record["pricing_version"] == "2026-07-byok-v1"
    assert record["billing_policy"] == "byok"
    assert record["billing_scope"] == "maestro_usage_units"
    assert record["provider_cost_included"] is False
    assert record["endpoint_class"] == "governance_evaluation"
    assert record["units_charged"] == 5
    assert record["quota_scope"] == "evaluation"
    assert record["plan_id"] == "business"
    assert record["quota_limit"] == 100
    assert record["quota_used"] == 98
    assert record["quota_requested"] == 5
    assert record["quota_remaining"] == 2
    assert record["quota_before"] == 93
    assert record["quota_after"] == 98
    assert record["quota_rejected"] is True
