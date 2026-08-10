from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from processual_api.admin_marketplace.lemon_squeezy_inbox import (
    LemonSqueezyWebhookIngestionResult,
    ingest_verified_lemon_squeezy_webhook,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    parse_verified_lemon_squeezy_webhook,
)


class LemonSqueezyIngestionUnitOfWork(Protocol):
    lemon_squeezy_webhook_inbox: object

    async def __aenter__(self) -> LemonSqueezyIngestionUnitOfWork: ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


def ingest_lemon_squeezy_webhook_request_factory(
    *,
    uow_factory: Callable[[], LemonSqueezyIngestionUnitOfWork],
):
    async def ingest_request(
        *,
        raw_body: bytes,
        signature: str,
        signing_secret: str,
        event_header: str,
        expected_store_id: str,
        received_at: datetime | None = None,
    ) -> LemonSqueezyWebhookIngestionResult:
        webhook = parse_verified_lemon_squeezy_webhook(
            raw_body=raw_body,
            signature=signature,
            signing_secret=signing_secret,
            event_header=event_header,
            expected_store_id=expected_store_id,
        )

        async with uow_factory() as uow:
            result = await ingest_verified_lemon_squeezy_webhook(
                repository=uow.lemon_squeezy_webhook_inbox,
                webhook=webhook,
                raw_body=raw_body,
                received_at=received_at,
            )
            await uow.commit()
            return result

    return ingest_request
