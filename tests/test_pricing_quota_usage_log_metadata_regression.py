from __future__ import annotations

import asyncio
import json

from starlette.requests import Request
from starlette.responses import Response

import processual_api.middleware.usage_log as usage_log_module
import processual_api.services.usage_log_store as usage_log_store
from processual_api.middleware.usage_log import UsageLogMiddleware


def _request(path: str) -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    })


def test_usage_log_middleware_attaches_quota_metadata(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(usage_log_module, "append_usage_log", captured.append)

    request = _request("/cgt/govern/auto-repair")
    request.state.current_user = {
        "auth_method": "api_key",
        "client_id": "integration-client",
        "user_id": "integration-user",
        "api_key_id": "key_123",
        "api_key_prefix": "pmk_test",
        "session_type": "service_integration",
        "role": "service",
        "quota": {
            "scope": "evaluation",
            "plan_id": "enterprise_integration",
            "limit": 500_000,
            "used": 125,
            "requested": 5,
            "remaining": 499_875,
        },
    }

    async def call_next(_request: Request) -> Response:
        return Response(
            status_code=200,
            headers={"X-Request-ID": "req-quota-log-001"},
        )

    middleware = UsageLogMiddleware(app=lambda scope, receive, send: None)
    asyncio.run(middleware.dispatch(request, call_next))

    assert len(captured) == 1
    record = captured[0]

    assert record["endpoint"] == "/cgt/govern/auto-repair"
    assert record["units_charged"] == 5
    assert record["quota_scope"] == "evaluation"
    assert record["quota_limit"] == 500_000
    assert record["quota_used"] == 125
    assert record["quota_requested"] == 5
    assert record["quota_remaining"] == 499_875
    assert record["quota_before"] == 120
    assert record["quota_after"] == 125
    assert record["plan_id"] == "enterprise_integration"


def test_usage_log_store_persists_quota_metadata(tmp_path, monkeypatch):
    usage_log_path = tmp_path / "usage_logs.jsonl"

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    usage_log_store.append_usage_log({
        "request_id": "req-quota-store-001",
        "client_id": "integration-client",
        "user_id": "integration-user",
        "api_key_id": "key_123",
        "api_key_prefix": "pmk_test",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "method": "POST",
        "endpoint": "/cgt/govern/auto-repair",
        "status_code": 200,
        "latency_ms": 1.25,
        "role": "service",
        "units_charged": 5,
        "quota_scope": "evaluation",
        "quota_limit": 500_000,
        "quota_used": 125,
        "quota_requested": 5,
        "quota_remaining": 499_875,
        "quota_before": 120,
        "quota_after": 125,
        "plan_id": "enterprise_integration",
    })

    records = [
        json.loads(line)
        for line in usage_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 1
    record = records[0]

    assert record["pricing_version"] == "2026-07-byok-v1"
    assert record["billing_policy"] == "byok"
    assert record["billing_scope"] == "maestro_usage_units"
    assert record["provider_cost_included"] is False
    assert record["endpoint_class"] == "governance_evaluation"
    assert record["units_charged"] == 5
    assert record["quota_scope"] == "evaluation"
    assert record["quota_limit"] == 500_000
    assert record["quota_used"] == 125
    assert record["quota_requested"] == 5
    assert record["quota_remaining"] == 499_875
    assert record["quota_before"] == 120
    assert record["quota_after"] == 125
    assert record["plan_id"] == "enterprise_integration"


def test_usage_log_store_derives_quota_before_when_only_after_is_given(
    tmp_path,
    monkeypatch,
):
    usage_log_path = tmp_path / "usage_logs.jsonl"

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    usage_log_store.append_usage_log({
        "method": "POST",
        "endpoint": "/cgt/govern/report",
        "units_charged": 3,
        "quota_after": 20,
        "quota_requested": 3,
    })

    record = json.loads(usage_log_path.read_text(encoding="utf-8").splitlines()[0])

    assert record["units_charged"] == 3
    assert record["quota_before"] == 17
    assert record["quota_after"] == 20
    assert record["quota_requested"] == 3
