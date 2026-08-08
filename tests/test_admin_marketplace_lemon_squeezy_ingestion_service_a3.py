from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from processual_api.admin_marketplace.lemon_squeezy_ingestion_service import (
    ingest_lemon_squeezy_webhook_request_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


SECRET = "super-secret"
NOW = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)


def _body(*, customer_ref: str = "customer-1") -> bytes:
    return json.dumps(
        {
            "meta": {
                "event_name": "subscription_updated",
                "custom_data": {
                    "customer_ref": customer_ref,
                    "order_ref": "order-1",
                    "offer_ref": "offer-1",
                },
            },
            "data": {
                "type": "subscriptions",
                "id": "123",
                "attributes": {"store_id": 42, "test_mode": False},
            },
        },
        separators=(",", ":"),
    ).encode()


def _signature(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


class FakeRepository:
    def __init__(self) -> None:
        self.by_identity = None
        self.by_payload = None
        self.added = []

    async def get_by_event_identity_hash(self, value, *, for_update=False):
        assert for_update is True
        return self.by_identity

    async def get_by_payload_digest(self, value, *, for_update=False):
        assert for_update is True
        return self.by_payload

    def add(self, value) -> None:
        self.added.append(value)


class FakeUow:
    def __init__(self) -> None:
        self.lemon_squeezy_webhook_inbox = FakeRepository()
        self.commit_count = 0
        self.entered = False
        self.exited = False
        self.exit_exception = None

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True
        self.exit_exception = exc

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_service_verifies_ingests_and_commits_once() -> None:
    uow = FakeUow()
    service = ingest_lemon_squeezy_webhook_request_factory(uow_factory=lambda: uow)
    body = _body()

    result = await service(
        raw_body=body,
        signature=_signature(body),
        signing_secret=SECRET,
        event_header="subscription_updated",
        expected_store_id="42",
        received_at=NOW,
    )

    assert result.replayed is False
    assert len(uow.lemon_squeezy_webhook_inbox.added) == 1
    assert uow.commit_count == 1
    assert uow.entered is True
    assert uow.exited is True
    assert uow.exit_exception is None


@pytest.mark.asyncio
async def test_invalid_signature_never_opens_transaction() -> None:
    uow = FakeUow()
    service = ingest_lemon_squeezy_webhook_request_factory(uow_factory=lambda: uow)
    body = _body()

    with pytest.raises(LemonSqueezyWebhookError):
        await service(
            raw_body=body,
            signature="0" * 64,
            signing_secret=SECRET,
            event_header="subscription_updated",
            expected_store_id="42",
            received_at=NOW,
        )

    assert uow.entered is False
    assert uow.commit_count == 0
    assert uow.lemon_squeezy_webhook_inbox.added == []


@pytest.mark.asyncio
async def test_ingestion_failure_exits_without_commit() -> None:
    uow = FakeUow()
    existing = type(
        "Existing",
        (),
        {
            "payload_digest": "0" * 64,
            "event_name": "subscription_updated",
            "resource_type": "subscriptions",
            "external_resource_id": "123",
            "store_id": "42",
            "customer_ref": "other-customer",
            "order_ref": "order-1",
            "offer_ref": "offer-1",
            "test_mode": False,
        },
    )()
    uow.lemon_squeezy_webhook_inbox.by_identity = existing
    service = ingest_lemon_squeezy_webhook_request_factory(uow_factory=lambda: uow)
    body = _body()

    with pytest.raises(LemonSqueezyWebhookError):
        await service(
            raw_body=body,
            signature=_signature(body),
            signing_secret=SECRET,
            event_header="subscription_updated",
            expected_store_id="42",
            received_at=NOW,
        )

    assert uow.entered is True
    assert uow.exited is True
    assert isinstance(uow.exit_exception, LemonSqueezyWebhookError)
    assert uow.commit_count == 0


def test_service_module_has_no_activation_or_reconciliation_api() -> None:
    import processual_api.admin_marketplace.lemon_squeezy_ingestion_service as module

    forbidden = {
        "activate_subscription",
        "activate_entitlements",
        "reconcile_payment",
        "process_subscription",
    }

    assert forbidden.isdisjoint(set(dir(module)))
