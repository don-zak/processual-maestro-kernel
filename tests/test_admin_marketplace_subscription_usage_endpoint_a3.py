from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from processual_api.admin_marketplace import subscription_usage_router as transport
from processual_api.admin_marketplace.router import router
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)


class _Recorder:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _body() -> transport.SubscriptionUsageRequest:
    return transport.SubscriptionUsageRequest(
        subscription_id=uuid.UUID("00000000-0000-0000-0000-000000000111"),
        metric_code="workflow_runs",
        units=3,
        dimensions={"region": "tn"},
    )


def test_usage_route_is_registered_once_and_requires_identity_dependency() -> None:
    routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == "/admin-marketplace/subscriptions/usage"
        and "POST" in route.methods
    ]
    assert len(routes) == 1
    endpoint = routes[0].endpoint
    assert endpoint is transport.record_subscription_usage_endpoint
    source = inspect.getsource(endpoint)
    assert "get_identity_user" in source
    assert "customer_ref" not in transport.SubscriptionUsageRequest.model_fields


def test_usage_contract_forbids_extra_customer_binding_and_invalid_units() -> None:
    with pytest.raises(ValidationError):
        transport.SubscriptionUsageRequest(
            subscription_id=uuid.uuid4(),
            metric_code="workflow_runs",
            units=1,
            dimensions={},
            customer_ref="attacker",
        )
    with pytest.raises(ValidationError):
        transport.SubscriptionUsageRequest(
            subscription_id=uuid.uuid4(),
            metric_code="workflow_runs",
            units=0,
            dimensions={},
        )


@pytest.mark.asyncio
async def test_endpoint_derives_customer_from_identity_and_passes_idempotency(monkeypatch) -> None:
    customer_id = uuid.UUID("00000000-0000-0000-0000-000000000222")
    usage = SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000333"),
        subscription_id=_body().subscription_id,
        metric_code="workflow_runs",
        units=3,
    )
    recorder = _Recorder(result=usage)
    monkeypatch.setattr(
        transport,
        "record_subscription_usage_factory",
        lambda **kwargs: recorder,
    )

    response = await transport.record_subscription_usage_endpoint(
        _body(),
        current_user={"user_id": str(customer_id), "session_type": "identity_user"},
        idempotency_key="usage-request-1",
    )

    assert response.usage_id == usage.id
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["customer_ref"] == str(customer_id)
    assert call["idempotency_key"] == "usage-request-1"
    assert "customer_ref" not in _body().model_dump()


@pytest.mark.asyncio
async def test_invalid_identity_fails_before_service_factory(monkeypatch) -> None:
    opened = False

    def factory(**kwargs):
        nonlocal opened
        opened = True
        return _Recorder()

    monkeypatch.setattr(transport, "record_subscription_usage_factory", factory)
    with pytest.raises(HTTPException) as captured:
        await transport.record_subscription_usage_endpoint(
            _body(),
            current_user={"user_id": "not-a-uuid", "session_type": "identity_user"},
            idempotency_key="usage-request-1",
        )
    assert captured.value.status_code == 403
    assert captured.value.detail == "Usage recording denied."
    assert opened is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (SubscriptionRuntimeError("quota limit exceeded."), 409),
        (SubscriptionRuntimeError("subscription customer binding mismatch."), 403),
    ],
)
async def test_domain_errors_are_sanitized(monkeypatch, error, expected_status) -> None:
    monkeypatch.setattr(
        transport,
        "record_subscription_usage_factory",
        lambda **kwargs: _Recorder(error=error),
    )
    with pytest.raises(HTTPException) as captured:
        await transport.record_subscription_usage_endpoint(
            _body(),
            current_user={
                "user_id": "00000000-0000-0000-0000-000000000222",
                "session_type": "identity_user",
            },
            idempotency_key="usage-request-1",
        )
    assert captured.value.status_code == expected_status
    assert captured.value.detail == "Usage recording denied."
    assert "quota" not in captured.value.detail.lower()
    assert "customer" not in captured.value.detail.lower()


@pytest.mark.asyncio
async def test_unexpected_failures_are_sanitized_as_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        transport,
        "record_subscription_usage_factory",
        lambda **kwargs: _Recorder(error=RuntimeError("database details")),
    )
    with pytest.raises(HTTPException) as captured:
        await transport.record_subscription_usage_endpoint(
            _body(),
            current_user={
                "user_id": "00000000-0000-0000-0000-000000000222",
                "session_type": "identity_user",
            },
            idempotency_key="usage-request-1",
        )
    assert captured.value.status_code == 503
    assert captured.value.detail == "Usage service is temporarily unavailable."
    assert "database" not in captured.value.detail.lower()
