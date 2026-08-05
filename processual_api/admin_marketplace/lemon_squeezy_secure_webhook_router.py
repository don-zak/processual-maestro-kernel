from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute

from processual_api.admin_marketplace.lemon_squeezy_ingestion_service import (
    ingest_lemon_squeezy_webhook_request_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.db.session import get_session_factory

_MAX_BODY_BYTES = 1_048_576
_MIN_SECRET_LENGTH = 32
_secure_router = APIRouter(prefix="/billing", tags=["billing"])


def _webhook_configuration() -> tuple[str, str]:
    signing_secret = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip()
    store_id = os.environ.get("LEMONSQUEEZY_STORE_ID", "").strip()
    if len(signing_secret) < _MIN_SECRET_LENGTH:
        raise HTTPException(status_code=503, detail="Webhook processing is unavailable.")
    if not store_id.isdigit() or int(store_id) <= 0:
        raise HTTPException(status_code=503, detail="Webhook processing is unavailable.")
    return signing_secret, store_id


def _uow_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
    return SqlAlchemyAdminMarketplaceUnitOfWork(get_session_factory())


@_secure_router.post("/webhook", include_in_schema=True)
async def secure_lemon_squeezy_webhook(request: Request) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook request.") from exc
        if declared_length < 0:
            raise HTTPException(status_code=400, detail="Invalid webhook request.")
        if declared_length > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook request is too large.")

    signing_secret, expected_store_id = _webhook_configuration()
    signature = request.headers.get("X-Signature", "")
    event_header = request.headers.get("X-Event-Name", "")
    raw_body = await request.body()
    if len(raw_body) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook request is too large.")

    ingest = ingest_lemon_squeezy_webhook_request_factory(uow_factory=_uow_factory)
    try:
        result = await ingest(
            raw_body=raw_body,
            signature=signature,
            signing_secret=signing_secret,
            event_header=event_header,
            expected_store_id=expected_store_id,
        )
    except LemonSqueezyWebhookError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook request.") from exc

    return {
        "received": True,
        "replayed": result.replayed,
        "inbox_id": str(result.entry.id),
    }


def install_secure_lemon_squeezy_webhook_route(target_router: APIRouter) -> None:
    target_router.routes[:] = [
        route
        for route in target_router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path == "/billing/webhook"
            and "POST" in route.methods
        )
    ]
    for route in reversed(_secure_router.routes):
        target_router.routes.insert(0, route)
