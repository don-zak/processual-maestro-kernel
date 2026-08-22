from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_ingestion_service import (
    ingest_lemon_squeezy_webhook_request_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    AdminMarketLemonSqueezyWebhookInbox,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)

DATABASE_URL = os.environ.get("ADMIN_MARKET_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "Set ADMIN_MARKET_INTEGRATION_DATABASE_URL to a migrated PostgreSQL "
        "database to run the Admin Marketplace commercial persistence gate."
    ),
)

SECRET = "integration-webhook-secret-material-32-bytes-minimum"
STORE_ID = "7001"
NOW = datetime(2026, 8, 22, 9, 30, tzinfo=UTC)


def _async_database_url() -> str:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


def _body(
    *,
    external_id: int,
    customer_ref: str,
    order_ref: str,
    offer_ref: str,
) -> bytes:
    return json.dumps(
        {
            "meta": {
                "event_name": "subscription_updated",
                "custom_data": {
                    "customer_ref": customer_ref,
                    "order_ref": order_ref,
                    "offer_ref": offer_ref,
                },
            },
            "data": {
                "type": "subscriptions",
                "id": str(external_id),
                "attributes": {
                    "store_id": int(STORE_ID),
                    "test_mode": True,
                    "customer_id": external_id + 1,
                    "order_id": external_id + 2,
                    "variant_id": external_id + 3,
                    "status": "active",
                    "updated_at": NOW.isoformat().replace("+00:00", "Z"),
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(body: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_signed_webhook_is_durable_replay_safe_and_conflict_closed() -> None:
    engine = create_async_engine(_async_database_url())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    service = ingest_lemon_squeezy_webhook_request_factory(
        uow_factory=lambda: SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)
    )

    suffix = uuid.uuid4().hex[:20]
    external_id = int(uuid.uuid4().int % 800_000_000) + 100_000_000
    customer_ref = f"pg-customer-{suffix}"
    order_ref = f"pg-order-{suffix}"
    offer_ref = f"pg-offer-{suffix}"
    body = _body(
        external_id=external_id,
        customer_ref=customer_ref,
        order_ref=order_ref,
        offer_ref=offer_ref,
    )

    inbox_id = None
    try:
        first = await service(
            raw_body=body,
            signature=_signature(body),
            signing_secret=SECRET,
            event_header="subscription_updated",
            expected_store_id=STORE_ID,
            received_at=NOW,
        )
        inbox_id = first.entry.id
        assert first.replayed is False

        second = await service(
            raw_body=body,
            signature=_signature(body),
            signing_secret=SECRET,
            event_header="subscription_updated",
            expected_store_id=STORE_ID,
            received_at=NOW,
        )
        assert second.replayed is True
        assert second.entry.id == inbox_id

        conflicting = _body(
            external_id=external_id,
            customer_ref=f"conflict-{suffix}",
            order_ref=order_ref,
            offer_ref=offer_ref,
        )
        with pytest.raises(LemonSqueezyWebhookError):
            await service(
                raw_body=conflicting,
                signature=_signature(conflicting),
                signing_secret=SECRET,
                event_header="subscription_updated",
                expected_store_id=STORE_ID,
                received_at=NOW,
            )

        with pytest.raises(LemonSqueezyWebhookError):
            await service(
                raw_body=body,
                signature="0" * 64,
                signing_secret=SECRET,
                event_header="subscription_updated",
                expected_store_id=STORE_ID,
                received_at=NOW,
            )

        async with session_factory() as session:
            persisted = await session.scalar(
                select(AdminMarketLemonSqueezyWebhookInbox).where(
                    AdminMarketLemonSqueezyWebhookInbox.id == inbox_id
                )
            )
            assert persisted is not None
            assert persisted.customer_ref == customer_ref
            assert persisted.order_ref == order_ref
            assert persisted.offer_ref == offer_ref
            assert persisted.processing_status == "received"
            assert persisted.attempt_count == 0

            row_count = await session.scalar(
                select(func.count())
                .select_from(AdminMarketLemonSqueezyWebhookInbox)
                .where(AdminMarketLemonSqueezyWebhookInbox.id == inbox_id)
            )
            assert row_count == 1
    finally:
        if inbox_id is not None:
            async with session_factory() as session:
                await session.execute(
                    delete(AdminMarketLemonSqueezyWebhookInbox).where(
                        AdminMarketLemonSqueezyWebhookInbox.id == inbox_id
                    )
                )
                await session.commit()
        await engine.dispose()
