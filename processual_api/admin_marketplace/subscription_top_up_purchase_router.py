from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from processual_api.admin_marketplace.lemon_squeezy_top_up_checkout import (
    CreateTopUpCheckoutCommand,
    LemonSqueezyTopUpCheckoutError,
    create_lemon_squeezy_top_up_checkout_factory,
    lemon_squeezy_http_checkout_creator_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_top_up_checkout_recovery import (
    LemonSqueezyTopUpCheckoutRecoveryError,
    RecoverTopUpCheckoutCommand,
    lemon_squeezy_http_checkout_finder_factory,
    recover_lemon_squeezy_top_up_checkout_factory,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.router import router
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_top_up_order import (
    CreateSubscriptionTopUpOrderCommand,
    SubscriptionTopUpOrderError,
    create_subscription_top_up_order_factory,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.plan_fulfillment_catalog import QUOTA_METRIC_CODE
from processual_api.db.session import get_session_factory

_TOP_UP_ORDER_NAMESPACE = uuid.UUID("ce8609b7-bab8-5d96-8ee7-177bd43f73ef")


class SubscriptionTopUpPurchaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    subscription_id: uuid.UUID
    requested_units: int = Field(gt=0, le=2_147_483_647)
    email: str | None = Field(default=None, max_length=320)


class SubscriptionTopUpPurchaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: uuid.UUID
    checkout_id: str
    checkout_url: str
    plan_code: str
    requested_units: int
    bundle_count: int
    total_price_usd: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class _LemonTopUpProviderConfig:
    api_key: str
    store_id: str
    variant_id: str
    success_url: str


def _uow_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
    return SqlAlchemyAdminMarketplaceUnitOfWork(get_session_factory())


def _identity_customer_ref(current_user: dict) -> str:
    try:
        return str(uuid.UUID(str(current_user["user_id"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Top-up purchase denied.") from exc


def _purchase_enabled() -> bool:
    return os.environ.get("MAESTRO_TOP_UP_PURCHASE_ENABLED", "false").strip().lower() == "true"


def _required_provider_config() -> _LemonTopUpProviderConfig:
    values = {
        "api_key": os.environ.get("LEMONSQUEEZY_API_KEY", "").strip(),
        "store_id": os.environ.get("LEMONSQUEEZY_STORE_ID", "").strip(),
        "variant_id": os.environ.get("LEMONSQUEEZY_TOP_UP_VARIANT_ID", "").strip(),
        "success_url": os.environ.get("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "").strip(),
    }
    if not all(values.values()):
        raise HTTPException(
            status_code=503,
            detail="Top-up purchase is temporarily unavailable.",
        )
    if not values["store_id"].isdigit() or not values["variant_id"].isdigit():
        raise HTTPException(
            status_code=503,
            detail="Top-up purchase is temporarily unavailable.",
        )
    if not values["success_url"].startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="Top-up purchase is temporarily unavailable.",
        )
    return _LemonTopUpProviderConfig(**values)


def _internal_idempotency_key(*, customer_ref: str, client_key: str) -> str:
    digest = hashlib.sha256(client_key.strip().encode("utf-8")).hexdigest()
    return f"top-up:{customer_ref}:{digest}"


def _deterministic_order_id(*, customer_ref: str, idempotency_key: str) -> uuid.UUID:
    material = f"maestro-top-up:{customer_ref}:{idempotency_key}"
    return uuid.uuid5(_TOP_UP_ORDER_NAMESPACE, material)


async def _resolve_current_cycle_id(
    *,
    subscription_id: uuid.UUID,
    customer_ref: str,
    at: datetime,
) -> uuid.UUID:
    session_factory = get_session_factory()
    async with session_factory() as session:
        statement = (
            select(AdminMarketSubscriptionQuotaCycle.id)
            .where(
                AdminMarketSubscriptionQuotaCycle.subscription_id == subscription_id,
                AdminMarketSubscriptionQuotaCycle.customer_ref == customer_ref,
                AdminMarketSubscriptionQuotaCycle.metric_code == QUOTA_METRIC_CODE,
                AdminMarketSubscriptionQuotaCycle.period_start <= at,
                AdminMarketSubscriptionQuotaCycle.period_end > at,
            )
            .order_by(AdminMarketSubscriptionQuotaCycle.period_start.desc())
            .limit(2)
        )
        cycle_ids = list((await session.scalars(statement)).all())
    if len(cycle_ids) != 1:
        raise SubscriptionTopUpOrderError(
            "top-up purchase requires exactly one current authoritative quota cycle."
        )
    return cycle_ids[0]


async def _retrieve_ready_checkout(
    *,
    api_key: str,
    checkout_id: str,
) -> tuple[str, str]:
    try:
        uuid.UUID(checkout_id)
    except ValueError as exc:
        raise LemonSqueezyTopUpCheckoutError("stored provider checkout id is invalid.") from exc

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"https://api.lemonsqueezy.com/v1/checkouts/{checkout_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/vnd.api+json",
                },
            )
    except httpx.HTTPError as exc:
        raise LemonSqueezyTopUpCheckoutError(
            "payment provider checkout retrieval failed."
        ) from exc

    if response.status_code != 200:
        raise LemonSqueezyTopUpCheckoutError(
            "payment provider checkout retrieval failed."
        )
    try:
        data = response.json()["data"]
        returned_id = str(data["id"]).strip()
        url = str(data["attributes"]["url"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise LemonSqueezyTopUpCheckoutError(
            "payment provider checkout response is invalid."
        ) from exc
    if returned_id != checkout_id or not url.startswith("https://"):
        raise LemonSqueezyTopUpCheckoutError(
            "payment provider checkout response conflicts with the order."
        )
    return returned_id, url


def _purchase_response(
    *,
    order_result: object,
    checkout_id: str,
    checkout_url: str,
    replayed: bool,
) -> SubscriptionTopUpPurchaseResponse:
    return SubscriptionTopUpPurchaseResponse(
        order_id=order_result.order_id,
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        plan_code=order_result.plan_code,
        requested_units=order_result.requested_units,
        bundle_count=order_result.bundle_count,
        total_price_usd=order_result.total_price_usd,
        replayed=replayed,
    )


@router.post(
    "/subscriptions/top-ups/purchase",
    response_model=SubscriptionTopUpPurchaseResponse,
    status_code=201,
)
async def purchase_subscription_top_up_endpoint(
    body: SubscriptionTopUpPurchaseRequest,
    current_user: dict = Depends(get_identity_user),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=255),
) -> SubscriptionTopUpPurchaseResponse:
    if not _purchase_enabled():
        raise HTTPException(status_code=503, detail="Top-up purchase is disabled.")

    provider = _required_provider_config()
    customer_ref = _identity_customer_ref(current_user)
    created_at = datetime.now(timezone.utc)
    internal_idempotency_key = _internal_idempotency_key(
        customer_ref=customer_ref,
        client_key=idempotency_key,
    )
    order_id = _deterministic_order_id(
        customer_ref=customer_ref,
        idempotency_key=internal_idempotency_key,
    )

    try:
        quota_cycle_id = await _resolve_current_cycle_id(
            subscription_id=body.subscription_id,
            customer_ref=customer_ref,
            at=created_at,
        )
        create_order = create_subscription_top_up_order_factory(
            unit_of_work_factory=_uow_factory,
        )
        order_result = await create_order(
            CreateSubscriptionTopUpOrderCommand(
                order_id=order_id,
                customer_ref=customer_ref,
                subscription_id=body.subscription_id,
                quota_cycle_id=quota_cycle_id,
                requested_units=body.requested_units,
                channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
                idempotency_key=internal_idempotency_key,
                created_at=created_at,
            )
        )
    except SubscriptionTopUpOrderError as exc:
        raise HTTPException(status_code=409, detail="Top-up purchase is not eligible.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Top-up purchase is temporarily unavailable.",
        ) from exc

    if order_result.idempotent_replay:
        recovery_required = False
        try:
            async with _uow_factory() as uow:
                existing = await uow.top_up_orders.get_by_id(order_id, for_update=False)
                if existing is None:
                    raise LemonSqueezyTopUpCheckoutError("top-up order was not found.")
                if existing.customer_ref != customer_ref:
                    raise LemonSqueezyTopUpCheckoutError(
                        "top-up checkout customer conflicts with the order."
                    )
                if existing.provider_variant_id not in {None, provider.variant_id}:
                    raise LemonSqueezyTopUpCheckoutError(
                        "checkout replay conflicts with the authoritative variant."
                    )
                if existing.checkout_creation_status == "ready":
                    if not existing.provider_checkout_id:
                        raise LemonSqueezyTopUpCheckoutError(
                            "ready checkout is missing provider checkout id."
                        )
                    checkout_id, checkout_url = await _retrieve_ready_checkout(
                        api_key=provider.api_key,
                        checkout_id=existing.provider_checkout_id,
                    )
                    return _purchase_response(
                        order_result=order_result,
                        checkout_id=checkout_id,
                        checkout_url=checkout_url,
                        replayed=True,
                    )
                recovery_required = existing.checkout_creation_status in {
                    "creating",
                    "uncertain",
                }
        except LemonSqueezyTopUpCheckoutError as exc:
            raise HTTPException(
                status_code=409,
                detail="Top-up checkout requires reconciliation.",
            ) from exc

        if recovery_required:
            recover_checkout = recover_lemon_squeezy_top_up_checkout_factory(
                unit_of_work_factory=_uow_factory,
                checkout_finder=lemon_squeezy_http_checkout_finder_factory(
                    api_key=provider.api_key,
                ),
            )
            try:
                recovered = await recover_checkout(
                    RecoverTopUpCheckoutCommand(
                        order_id=order_id,
                        customer_ref=customer_ref,
                        store_id=provider.store_id,
                        provider_variant_id=provider.variant_id,
                    )
                )
            except LemonSqueezyTopUpCheckoutRecoveryError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="Top-up checkout requires reconciliation.",
                ) from exc
            return _purchase_response(
                order_result=order_result,
                checkout_id=recovered.checkout_id,
                checkout_url=recovered.url,
                replayed=True,
            )

    create_checkout = create_lemon_squeezy_top_up_checkout_factory(
        unit_of_work_factory=_uow_factory,
        checkout_creator=lemon_squeezy_http_checkout_creator_factory(
            api_key=provider.api_key,
        ),
    )
    try:
        checkout = await create_checkout(
            CreateTopUpCheckoutCommand(
                order_id=order_id,
                customer_ref=customer_ref,
                provider_variant_id=provider.variant_id,
                store_id=provider.store_id,
                success_url=provider.success_url,
                email=body.email,
            )
        )
    except LemonSqueezyTopUpCheckoutError as exc:
        raise HTTPException(
            status_code=409,
            detail="Top-up checkout could not be created safely.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Top-up purchase is temporarily unavailable.",
        ) from exc

    return _purchase_response(
        order_result=order_result,
        checkout_id=checkout.checkout_id,
        checkout_url=checkout.url,
        replayed=False,
    )


__all__ = [
    "SubscriptionTopUpPurchaseRequest",
    "SubscriptionTopUpPurchaseResponse",
    "purchase_subscription_top_up_endpoint",
]
