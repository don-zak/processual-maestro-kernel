from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.auth import security
from processual_api.billing import usage_pricing
from processual_api.services import quota_store, sandbox_api_key_usage


DURABLE_USER = {
    "sub": "user-01",
    "user_id": "user-01",
    "client_id": "customer-01",
    "role": "client",
    "auth_method": "api_key",
    "session_type": "sandbox_api_key",
    "api_key_id": "11111111-1111-1111-1111-111111111111",
    "subscription_id": "22222222-2222-2222-2222-222222222222",
    "plan_id": "enterprise_pilot",
    "operational_profile_id": "service_integration_read_only",
    "environment": "sandbox",
    "scopes": ["read:health"],
    "production_allowed": False,
    "runtime_connector_approved": False,
}


def _request(*, idempotency_key: str = "request-01") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/analyze",
            "headers": [(b"idempotency-key", idempotency_key.encode("ascii"))],
        }
    )


def _pricing(units: int = 3):
    return SimpleNamespace(
        endpoint="/v1/analyze",
        endpoint_class="analysis",
        units_charged=units,
        billing_scope="maestro_units",
        pricing_version="qualification",
    )


def _dependency():
    return security.require_quota("evaluation")


def test_durable_sandbox_usage_records_to_subscription_ledger_only(monkeypatch) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**kwargs):
        assert kwargs["current_user"] == DURABLE_USER
        assert kwargs["metric_code"] == "maestro_units"
        assert kwargs["units"] == 3
        assert kwargs["endpoint"] == "/v1/analyze"
        assert kwargs["idempotency_key"].startswith("sandbox-api-key:")
        return SimpleNamespace(id=uuid.UUID("33333333-3333-3333-3333-333333333333"))

    monkeypatch.setattr(sandbox_api_key_usage, "record_sandbox_api_key_usage", _record)

    def _legacy(*_args, **_kwargs):
        raise AssertionError("legacy quota store must not run for durable sandbox keys")

    monkeypatch.setattr(quota_store, "consume_quota", _legacy)

    request = _request()
    result = asyncio.run(_dependency()(request, DURABLE_USER))

    assert result["quota"]["source"] == "subscription_usage_ledger"
    assert result["quota"]["charged"] == 3
    assert result["quota"]["rejected"] is False
    assert request.state.current_user == result


def test_durable_quota_exhaustion_is_429_without_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**_kwargs):
        raise SubscriptionRuntimeError("quota limit exceeded.")

    monkeypatch.setattr(sandbox_api_key_usage, "record_sandbox_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy quota store must not run after durable quota denial")
        ),
    )

    request = _request()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_dependency()(request, DURABLE_USER))

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "quota_exceeded"
    assert exc.value.detail["quota_source"] == "subscription_usage_ledger"
    assert request.state.current_user["quota_rejected"] is True


def test_durable_usage_authority_failure_is_503_and_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(sandbox_api_key_usage, "record_sandbox_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy quota store must not run after durable DB failure")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_dependency()(_request(), DURABLE_USER))

    assert exc.value.status_code == 503
    assert exc.value.detail == "Subscription usage authority unavailable."


def test_free_durable_request_skips_ledger_and_legacy_quota(monkeypatch) -> None:
    monkeypatch.setattr(
        usage_pricing,
        "pricing_decision",
        lambda *_args, **_kwargs: _pricing(units=0),
    )

    async def _record(**_kwargs):
        raise AssertionError("free request must not create durable usage")

    monkeypatch.setattr(sandbox_api_key_usage, "record_sandbox_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("free durable request must not use legacy quota")
        ),
    )

    result = asyncio.run(_dependency()(_request(), DURABLE_USER))

    assert result == DURABLE_USER
