from __future__ import annotations

import asyncio
import json

from starlette.requests import Request
from starlette.responses import Response

import processual_api.middleware.usage_log as usage_log_module
import processual_api.services.usage_log_store as usage_log_store
from processual_api.middleware.usage_log import UsageLogMiddleware


def test_usage_log_middleware_attaches_byok_pricing_metadata(monkeypatch):
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(usage_log_module, "append_usage_log", captured.append)

    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/cgt/govern",
        "raw_path": b"/cgt/govern",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
    })
    request.state.current_user = {
        "auth_method": "api_key",
        "client_id": "integration-client",
        "user_id": "integration-user",
        "api_key_id": "key_123",
        "api_key_prefix": "pmk_test",
        "session_type": "service_integration",
        "role": "service",
    }

    async def call_next(_request: Request) -> Response:
        return Response(
            status_code=200,
            headers={"X-Request-ID": "req-pricing-001"},
        )

    middleware = UsageLogMiddleware(app=lambda scope, receive, send: None)
    asyncio.run(middleware.dispatch(request, call_next))

    assert len(captured) == 1
    record = captured[0]

    assert record["endpoint"] == "/cgt/govern"
    assert record["pricing_version"] == "2026-07-byok-v1"
    assert record["billing_policy"] == "byok"
    assert record["billing_scope"] == "maestro_usage_units"
    assert record["provider_cost_included"] is False
    assert record["endpoint_class"] == "governance_evaluation"
    assert record["units_charged"] == 1


def test_usage_log_store_persists_byok_pricing_metadata(tmp_path, monkeypatch):
    usage_log_path = tmp_path / "usage_logs.jsonl"

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", usage_log_path)

    usage_log_store.append_usage_log({
        "request_id": "req-pricing-store-001",
        "client_id": "integration-client",
        "user_id": "integration-user",
        "api_key_id": "key_123",
        "api_key_prefix": "pmk_test",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "method": "GET",
        "endpoint": "/settings/subscription",
        "status_code": 200,
        "latency_ms": 1.25,
        "role": "service",
    })

    records = [
        json.loads(line)
        for line in usage_log_path.read_text(encoding="utf-8").splitlines()
    ]

    assert len(records) == 1
    record = records[0]

    assert record["endpoint"] == "/settings/subscription"
    assert record["pricing_version"] == "2026-07-byok-v1"
    assert record["billing_policy"] == "byok"
    assert record["billing_scope"] == "maestro_usage_units"
    assert record["provider_cost_included"] is False
    assert record["endpoint_class"] == "free_operational_check"
    assert record["units_charged"] == 0
