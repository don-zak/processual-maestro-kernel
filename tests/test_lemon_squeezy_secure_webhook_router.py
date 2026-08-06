from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import processual_api.admin_marketplace.lemon_squeezy_secure_webhook_router as router
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


async def _request(
    body: bytes = b"{}",
    *,
    signature: str = "signature",
    event_name: str = "subscription_updated",
) -> Request:
    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/billing/webhook",
            "headers": [
                (b"content-length", str(len(body)).encode("ascii")),
                (b"x-signature", signature.encode("ascii")),
                (b"x-event-name", event_name.encode("ascii")),
            ],
        },
        receive,
    )


def _configure(monkeypatch: pytest.MonkeyPatch, *, environment: str = "production") -> None:
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", "s" * 32)
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "7001")
    monkeypatch.setattr(router.settings, "environment", environment)


@pytest.mark.asyncio
async def test_secure_webhook_ingests_then_reconciles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    inbox_id = uuid.uuid4()
    calls: list[str] = []

    def ingest_factory(*, uow_factory: object):
        assert uow_factory is router._uow_factory

        async def ingest(**kwargs: object):
            calls.append("ingest")
            assert kwargs["expected_store_id"] == "7001"
            return SimpleNamespace(
                replayed=False,
                entry=SimpleNamespace(id=inbox_id),
            )

        return ingest

    def loader_factory(*, production_mode: bool):
        assert production_mode is True
        return object()

    def process_factory(*, uow_factory: object, context_loader: object):
        assert uow_factory is router._uow_factory
        assert context_loader is not None

        async def process(*, inbox_id: uuid.UUID):
            calls.append("process")
            assert inbox_id == inbox_id_expected
            return SimpleNamespace(
                action="reconcile",
                reason_code="verified_evidence_requires_reconciliation",
            )

        inbox_id_expected = inbox_id
        return process

    monkeypatch.setattr(router, "ingest_lemon_squeezy_webhook_request_factory", ingest_factory)
    monkeypatch.setattr(
        router,
        "lemon_squeezy_reconciliation_context_loader_factory",
        loader_factory,
    )
    monkeypatch.setattr(
        router,
        "process_lemon_squeezy_reconciliation_factory",
        process_factory,
    )

    response = await router.secure_lemon_squeezy_webhook(await _request())

    assert calls == ["ingest", "process"]
    assert response == {
        "received": True,
        "replayed": False,
        "inbox_id": str(inbox_id),
        "reconciliation_action": "reconcile",
        "reconciliation_reason": "verified_evidence_requires_reconciliation",
    }


@pytest.mark.asyncio
async def test_ingestion_failure_remains_bad_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)

    def ingest_factory(*, uow_factory: object):
        async def ingest(**kwargs: object):
            raise LemonSqueezyWebhookError("invalid signature")

        return ingest

    monkeypatch.setattr(router, "ingest_lemon_squeezy_webhook_request_factory", ingest_factory)

    with pytest.raises(HTTPException) as exc_info:
        await router.secure_lemon_squeezy_webhook(await _request())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid webhook request."


@pytest.mark.asyncio
async def test_reconciliation_failure_returns_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    inbox_id = uuid.uuid4()

    def ingest_factory(*, uow_factory: object):
        async def ingest(**kwargs: object):
            return SimpleNamespace(
                replayed=False,
                entry=SimpleNamespace(id=inbox_id),
            )

        return ingest

    def process_factory(*, uow_factory: object, context_loader: object):
        async def process(*, inbox_id: uuid.UUID):
            raise LemonSqueezyWebhookError("binding conflict")

        return process

    monkeypatch.setattr(router, "ingest_lemon_squeezy_webhook_request_factory", ingest_factory)
    monkeypatch.setattr(
        router,
        "lemon_squeezy_reconciliation_context_loader_factory",
        lambda *, production_mode: object(),
    )
    monkeypatch.setattr(
        router,
        "process_lemon_squeezy_reconciliation_factory",
        process_factory,
    )

    with pytest.raises(HTTPException) as exc_info:
        await router.secure_lemon_squeezy_webhook(await _request())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Webhook reconciliation failed."


@pytest.mark.asyncio
async def test_unknown_environment_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, environment="mystery")

    with pytest.raises(HTTPException) as exc_info:
        await router.secure_lemon_squeezy_webhook(await _request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Webhook processing is unavailable."
