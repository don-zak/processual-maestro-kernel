import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import processual_api.middleware.audit as audit_module
import processual_api.middleware.rate_limit as rate_module
import processual_api.middleware.subscription as subscription_module
import processual_api.middleware.usage_log as usage_log_module
from processual_api.middleware.error_handler import error_handler_middleware
from processual_api.middleware.request_id import RequestIDMiddleware
from processual_api.middleware.security_headers import SecurityHeadersMiddleware
from processual_api.middleware.usage_log import UsageLogMiddleware


async def _ok_endpoint(request):
    return JSONResponse({"ok": True})


def _app_with_route(route="/ok", endpoint=_ok_endpoint):
    return Starlette(routes=[Route(route, endpoint)])


def _request(path="/boom"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "query_string": b"",
        }
    )


def test_request_id_and_security_headers_are_added():
    app = _app_with_route()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    client = TestClient(app)
    response = client.get("/ok", headers={"X-Request-ID": "rid-test-09a"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "rid-test-09a"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-xss-protection"] == "1; mode=block"
    assert response.headers["strict-transport-security"] == ("max-age=31536000; includeSubDomains")


def test_error_handler_returns_generic_500_response():
    async def failing_call_next(request):
        raise RuntimeError("sensitive internal failure")

    response = asyncio.run(error_handler_middleware(_request(), failing_call_next))

    assert response.status_code == 500
    assert json.loads(response.body.decode("utf-8")) == {"detail": "Internal server error"}
    assert "sensitive internal failure" not in response.body.decode("utf-8")


def test_parse_rate_limit_accepts_known_and_default_windows():
    assert rate_module._parse_rate_limit("10/second") == (10, 1)
    assert rate_module._parse_rate_limit("20/minute") == (20, 60)
    assert rate_module._parse_rate_limit("30/hour") == (30, 3600)
    assert rate_module._parse_rate_limit("40/day") == (40, 86400)
    assert rate_module._parse_rate_limit("5/custom") == (5, 60)
    assert rate_module._parse_rate_limit("7") == (7, 60)


def test_registration_routes_bypass_legacy_rate_limit_middleware(monkeypatch):
    class FailingRedis:
        async def incr(self, key):
            raise AssertionError("legacy limiter must not inspect registration")

    async def fake_get_redis():
        return FailingRedis()

    monkeypatch.setattr(rate_module, "get_redis", fake_get_redis)
    monkeypatch.setattr(rate_module.settings, "rate_limit_enabled", True)
    app = _app_with_route("/auth/register")
    app.add_middleware(rate_module.RateLimitMiddleware)

    response = TestClient(app).get("/auth/register")

    assert response.status_code == 200


def test_rate_limit_middleware_uses_redis_counter_and_returns_429(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.counts = {}
            self.expired = []

        async def incr(self, key):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

        async def expire(self, key, window):
            self.expired.append((key, window))

        async def ttl(self, key):
            return 33

    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(rate_module, "get_redis", fake_get_redis)
    monkeypatch.setattr(rate_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rate_module.settings, "rate_limit_default", "2/minute")
    monkeypatch.setattr(
        rate_module.settings,
        "rate_limit_authenticated",
        "5/minute",
    )

    app = _app_with_route("/limited")
    app.add_middleware(rate_module.RateLimitMiddleware)
    client = TestClient(app)

    headers = {"X-Forwarded-For": "10.0.0.7"}

    first = client.get("/limited", headers=headers)
    second = client.get("/limited", headers=headers)
    third = client.get("/limited", headers=headers)

    assert first.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"

    assert second.status_code == 200
    assert second.headers["x-ratelimit-remaining"] == "0"

    assert third.status_code == 429
    assert third.headers["retry-after"] == "33"
    assert third.headers["x-ratelimit-limit"] == "2"
    assert third.headers["x-ratelimit-remaining"] == "0"
    assert third.json()["detail"] == "Rate limit exceeded. Try again later."
    assert fake_redis.expired


def test_audit_middleware_logs_request_when_enabled(monkeypatch, caplog):
    monkeypatch.setattr(audit_module.settings, "audit_enabled", True)

    app = _app_with_route()
    app.add_middleware(audit_module.AuditMiddleware)
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger="processual.audit.trail"):
        response = client.get("/ok", headers={"X-Request-ID": "audit-test-09a"})

    assert response.status_code == 200
    assert "audit-test-09a" in caplog.text
    assert '"method": "GET"' in caplog.text
    assert '"path": "/ok"' in caplog.text
    assert '"status_code": 200' in caplog.text


def test_usage_log_middleware_records_api_key_user(monkeypatch):
    captured = []

    async def endpoint_with_api_key_user(request):
        request.state.current_user = {
            "auth_method": "api_key",
            "client_id": "client_1",
            "user_id": "user_1",
            "api_key_id": "key_1",
            "api_key_prefix": "pmk_test",
            "session_type": "customer",
            "role": "client",
        }
        return JSONResponse(
            {"ok": True},
            headers={"X-Request-ID": "usage-test-09a"},
        )

    monkeypatch.setattr(usage_log_module, "append_usage_log", captured.append)

    app = _app_with_route("/usage", endpoint_with_api_key_user)
    app.add_middleware(UsageLogMiddleware)
    client = TestClient(app)

    response = client.get("/usage")

    assert response.status_code == 200
    assert len(captured) == 1

    record = captured[0]
    assert record["request_id"] == "usage-test-09a"
    assert record["client_id"] == "client_1"
    assert record["user_id"] == "user_1"
    assert record["api_key_id"] == "key_1"
    assert record["api_key_prefix"] == "pmk_test"
    assert record["auth_method"] == "api_key"
    assert record["session_type"] == "customer"
    assert record["method"] == "GET"
    assert record["endpoint"] == "/usage"
    assert record["status_code"] == 200
    assert record["role"] == "client"
    assert isinstance(record["latency_ms"], float)


def test_usage_log_store_sanitizes_raw_api_key_in_endpoint(tmp_path, monkeypatch):
    import json

    import processual_api.services.usage_log_store as usage_log_store

    data_dir = tmp_path / "data"
    log_path = data_dir / "usage_logs.jsonl"

    monkeypatch.setattr(usage_log_store, "_DATA_DIR", data_dir)
    monkeypatch.setattr(usage_log_store, "_USAGE_LOG_PATH", log_path)

    raw_api_key = "pmk_secretRawKeyShouldNotLeak123"
    usage_log_store.append_usage_log(
        {
            "request_id": "usage-sanitize-01",
            "client_id": "client_1",
            "user_id": "user_1",
            "api_key_id": "key_1",
            "api_key_prefix": "pmk_secret...",
            "auth_method": "api_key",
            "session_type": "api_key",
            "method": "PATCH",
            "endpoint": f"/settings/api-keys/{raw_api_key}/plan",
            "status_code": 404,
            "latency_ms": 1.25,
            "role": "client",
        }
    )

    record = json.loads(log_path.read_text(encoding="utf-8").strip())

    assert record["endpoint"] == "/settings/api-keys/pmk_[redacted]/plan"
    assert raw_api_key not in json.dumps(record)
    assert record["api_key_id"] == "key_1"
    assert record["api_key_prefix"] == "pmk_secret..."


def test_subscription_stage_computation_for_billing_states():
    now = datetime.now(UTC)

    assert subscription_module._compute_stage({"status": "active"}) == "active"
    assert subscription_module._compute_stage({"status": "expired"}) == "expired"
    assert subscription_module._compute_stage({"status": "cancelled"}) == "expired"

    assert (
        subscription_module._compute_stage(
            {
                "status": "past_due",
                "suspended_at": (now - timedelta(days=3)).isoformat(),
            }
        )
        == "grace"
    )

    assert (
        subscription_module._compute_stage(
            {
                "status": "past_due",
                "suspended_at": (now - timedelta(days=20)).isoformat(),
            }
        )
        == "suspended"
    )

    assert (
        subscription_module._compute_stage(
            {
                "status": "past_due",
                "suspended_at": (now - timedelta(days=120)).isoformat(),
            }
        )
        == "expired"
    )

    assert (
        subscription_module._compute_stage(
            {
                "status": "past_due",
                "suspended_at": "not-a-date",
            }
        )
        == "grace"
    )
