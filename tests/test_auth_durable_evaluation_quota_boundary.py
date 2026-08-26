from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.auth import security
from processual_api.billing import usage_pricing
from processual_api.services import evaluation_grant_usage, quota_store


DURABLE_EVALUATION_USER = {
    "sub": "eval-user",
    "user_id": "eval-user",
    "client_id": "eval-client",
    "role": "client",
    "auth_method": "api_key",
    "session_type": "evaluation_api_key",
    "api_key_id": "evalkey_qualification",
    "api_key_authority_id": "11111111-1111-1111-1111-111111111111",
    "evaluation_grant_id": "eval_qualification",
    "evaluation_grant_authority_id": "22222222-2222-2222-2222-222222222222",
    "entitlement_source": "admin_evaluation_grant",
    "subscription_required": False,
    "scopes": ["read:health"],
    "quota_source": "evaluation_usage_ledger",
    "production_allowed": False,
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
        billing_scope="evaluation",
        pricing_version="qualification",
    )


def _dependency():
    return security.require_quota("evaluation")


def test_durable_evaluation_usage_records_to_evaluation_ledger_only(monkeypatch) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**kwargs):
        assert kwargs["current_user"] == DURABLE_EVALUATION_USER
        assert kwargs["units"] == 3
        assert kwargs["idempotency_key"].startswith("evaluation-api-key:")
        return SimpleNamespace(id=uuid.UUID("33333333-3333-3333-3333-333333333333"))

    monkeypatch.setattr(evaluation_grant_usage, "record_evaluation_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy quota store must not run for durable evaluation keys")
        ),
    )

    request = _request()
    result = asyncio.run(_dependency()(request, DURABLE_EVALUATION_USER))

    assert result["quota"]["source"] == "evaluation_usage_ledger"
    assert result["quota"]["charged"] == 3
    assert result["quota"]["rejected"] is False
    assert request.state.current_user == result


def test_durable_evaluation_quota_exhaustion_is_429_without_legacy_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**_kwargs):
        raise evaluation_grant_usage.EvaluationUsageError("evaluation_quota_limit_exceeded")

    monkeypatch.setattr(evaluation_grant_usage, "record_evaluation_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy quota store must not run after evaluation quota denial")
        ),
    )

    request = _request()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_dependency()(request, DURABLE_EVALUATION_USER))

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "quota_exceeded"
    assert exc.value.detail["quota_source"] == "evaluation_usage_ledger"
    assert request.state.current_user["quota_rejected"] is True


def test_durable_evaluation_usage_authority_failure_is_503_and_fail_closed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(usage_pricing, "pricing_decision", lambda *_args, **_kwargs: _pricing())

    async def _record(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(evaluation_grant_usage, "record_evaluation_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy quota store must not run after evaluation DB failure")
        ),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_dependency()(_request(), DURABLE_EVALUATION_USER))

    assert exc.value.status_code == 503
    assert exc.value.detail == "Evaluation usage authority unavailable."


def test_free_durable_evaluation_request_skips_both_quota_backends(monkeypatch) -> None:
    monkeypatch.setattr(
        usage_pricing,
        "pricing_decision",
        lambda *_args, **_kwargs: _pricing(units=0),
    )

    async def _record(**_kwargs):
        raise AssertionError("free evaluation request must not create durable usage")

    monkeypatch.setattr(evaluation_grant_usage, "record_evaluation_api_key_usage", _record)
    monkeypatch.setattr(
        quota_store,
        "consume_quota",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("free durable evaluation request must not use legacy quota")
        ),
    )

    result = asyncio.run(_dependency()(_request(), DURABLE_EVALUATION_USER))
    assert result == DURABLE_EVALUATION_USER
