from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.requests import Request

from processual_api.auth.delivery_contracts import (
    DeliveryOperationalMetrics,
    DeliveryRedriveResult,
)
from processual_api.auth.delivery_operations_http_contracts import (
    DeliveryOperationalMetricsResponseContract,
    DeliveryRedriveAcceptedResponseContract,
)
from processual_api.auth.delivery_operations_router import (
    GENERIC_UNAVAILABLE,
    delivery_operational_metrics,
    get_delivery_operations_runtime,
    platform_admin_step_up_dependency,
    redrive_dead_letter_delivery,
    router,
)
from processual_api.auth.delivery_operations_runtime import (
    DeliveryOperationsRuntimeUnavailableError,
)
from processual_api.auth.delivery_operations_service import (
    DeliveryRedriveUnavailableError,
)


def _request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    request.state.request_id = "r9c-test-request"
    return request


class FakeService:
    def __init__(
        self,
        *,
        metrics_result=None,
        redrive_result=None,
        redrive_error=None,
        metrics_error=None,
    ) -> None:
        self.metrics_result = metrics_result
        self.redrive_result = redrive_result
        self.redrive_error = redrive_error
        self.metrics_error = metrics_error
        self.metrics_calls = 0
        self.redrive_calls = []

    async def metrics(self):
        self.metrics_calls += 1

        if self.metrics_error is not None:
            raise self.metrics_error

        return self.metrics_result

    async def redrive(
        self,
        *,
        outbox_id: uuid.UUID,
    ):
        self.redrive_calls.append(outbox_id)

        if self.redrive_error is not None:
            raise self.redrive_error

        return self.redrive_result


def _runtime(service):
    return SimpleNamespace(service=service)


def _body(response: JSONResponse):
    return json.loads(response.body.decode("utf-8"))


def test_http_contracts_forbid_extra_and_negative_values():
    with pytest.raises(ValidationError):
        DeliveryOperationalMetricsResponseContract(
            pending_count=-1,
            retry_scheduled_count=0,
            leased_count=0,
            dead_letter_count=0,
            delivered_count=0,
        )

    with pytest.raises(ValidationError):
        DeliveryRedriveAcceptedResponseContract(
            status="accepted",
            secret="forbidden",
        )


def test_router_registers_exact_protected_operations():
    routes = {
        (
            route.path,
            tuple(sorted(route.methods or ())),
        ): route
        for route in router.routes
    }

    metrics_key = (
        "/auth/delivery-operations/metrics",
        ("GET",),
    )
    redrive_key = (
        (
            "/auth/delivery-operations"
            "/dead-letters/{outbox_id}/redrive"
        ),
        ("POST",),
    )

    assert metrics_key in routes
    assert redrive_key in routes

    for key in (metrics_key, redrive_key):
        dependency_calls = {
            dependency.call
            for dependency in (
                routes[key].dependant.dependencies
            )
        }

        assert (
            platform_admin_step_up_dependency
            in dependency_calls
        )
        assert get_delivery_operations_runtime in (
            dependency_calls
        )


@pytest.mark.asyncio
async def test_metrics_maps_only_safe_operational_fields():
    metrics = DeliveryOperationalMetrics(
        pending_count=4,
        retry_scheduled_count=3,
        leased_count=2,
        dead_letter_count=1,
        delivered_count=9,
        oldest_pending_age_seconds=120,
    )
    service = FakeService(metrics_result=metrics)

    response = await delivery_operational_metrics(
        request=_request(),
        current_user={"user_id": str(uuid.uuid4())},
        runtime=_runtime(service),
    )

    assert response.model_dump() == {
        "pending_count": 4,
        "retry_scheduled_count": 3,
        "leased_count": 2,
        "dead_letter_count": 1,
        "delivered_count": 9,
        "oldest_pending_age_seconds": 120,
    }
    assert service.metrics_calls == 1


@pytest.mark.asyncio
async def test_metrics_failure_is_generic():
    service = FakeService(
        metrics_error=RuntimeError(
            "database details must not escape"
        )
    )

    with pytest.raises(HTTPException) as raised:
        await delivery_operational_metrics(
            request=_request(),
            current_user={"user_id": str(uuid.uuid4())},
            runtime=_runtime(service),
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == GENERIC_UNAVAILABLE
    assert "database details" not in raised.value.detail


@pytest.mark.asyncio
async def test_redrive_success_returns_generic_acceptance():
    now = datetime(
        2026,
        7,
        24,
        15,
        0,
        tzinfo=UTC,
    )
    outbox_id = uuid.uuid4()
    service = FakeService(
        redrive_result=DeliveryRedriveResult(
            outbox_id=outbox_id,
            available_at=now,
            preserved_attempt_count=8,
        )
    )

    response = await redrive_dead_letter_delivery(
        outbox_id=outbox_id,
        request=_request(),
        current_user={"user_id": str(uuid.uuid4())},
        runtime=_runtime(service),
    )

    assert response.status_code == 202
    assert _body(response) == {"status": "accepted"}
    assert service.redrive_calls == [outbox_id]


@pytest.mark.asyncio
async def test_redrive_ineligible_row_is_non_enumerable():
    outbox_id = uuid.uuid4()
    service = FakeService(
        redrive_error=DeliveryRedriveUnavailableError(
            "row does not exist"
        )
    )

    response = await redrive_dead_letter_delivery(
        outbox_id=outbox_id,
        request=_request(),
        current_user={"user_id": str(uuid.uuid4())},
        runtime=_runtime(service),
    )

    assert response.status_code == 202
    assert _body(response) == {"status": "accepted"}
    assert "exist" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_redrive_unexpected_failure_is_generic():
    outbox_id = uuid.uuid4()
    service = FakeService(
        redrive_error=RuntimeError(
            "provider and database internals"
        )
    )

    response = await redrive_dead_letter_delivery(
        outbox_id=outbox_id,
        request=_request(),
        current_user={"user_id": str(uuid.uuid4())},
        runtime=_runtime(service),
    )

    assert response.status_code == 503
    assert _body(response) == {
        "detail": GENERIC_UNAVAILABLE
    }
    assert "provider" not in response.body.decode("utf-8")
    assert "database" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_runtime_dependency_maps_unavailable_error(
    monkeypatch,
):
    async def fail_runtime():
        raise DeliveryOperationsRuntimeUnavailableError(
            "database authority details"
        )

    monkeypatch.setattr(
        (
            "processual_api.auth"
            ".delivery_operations_router"
            ".build_delivery_operations_runtime"
        ),
        fail_runtime,
    )

    with pytest.raises(HTTPException) as raised:
        await get_delivery_operations_runtime()

    assert raised.value.status_code == 503
    assert raised.value.detail == GENERIC_UNAVAILABLE
    assert "database authority" not in raised.value.detail
