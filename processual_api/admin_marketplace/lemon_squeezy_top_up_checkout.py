from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_CATALOG_VERSION

_TOP_UP_OFFER_REF = "quota_top_up"


class LemonSqueezyTopUpCheckoutError(RuntimeError):
    """A top-up checkout cannot be created or rebound safely."""


@dataclass(frozen=True, slots=True)
class LemonSqueezyCheckoutRequest:
    store_id: str
    variant_id: str
    customer_ref: str
    order_ref: str
    subtotal_usd: Decimal
    email: str | None
    success_url: str


@dataclass(frozen=True, slots=True)
class LemonSqueezyCheckoutResponse:
    checkout_id: str
    url: str


class LemonSqueezyCheckoutCreator(Protocol):
    async def __call__(
        self,
        request: LemonSqueezyCheckoutRequest,
    ) -> LemonSqueezyCheckoutResponse: ...


@dataclass(frozen=True, slots=True)
class CreateTopUpCheckoutCommand:
    order_id: uuid.UUID
    customer_ref: str
    provider_variant_id: str
    store_id: str
    success_url: str
    email: str | None = None


@dataclass(frozen=True, slots=True)
class CreateTopUpCheckoutResult:
    order_id: uuid.UUID
    checkout_id: str
    url: str
    provider_variant_id: str
    replayed: bool
    committed: bool


def create_lemon_squeezy_top_up_checkout_factory(
    *,
    unit_of_work_factory: Callable[[], object],
    checkout_creator: LemonSqueezyCheckoutCreator,
):
    async def create(command: CreateTopUpCheckoutCommand) -> CreateTopUpCheckoutResult:
        _validate(command)

        async with unit_of_work_factory() as uow:
            order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
            if order is None:
                raise LemonSqueezyTopUpCheckoutError("top-up order was not found.")
            if order.customer_ref != command.customer_ref:
                raise LemonSqueezyTopUpCheckoutError(
                    "top-up checkout customer conflicts with the order."
                )
            if order.channel != "lemon_squeezy":
                raise LemonSqueezyTopUpCheckoutError(
                    "top-up order is not assigned to Lemon Squeezy."
                )
            if order.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION:
                raise LemonSqueezyTopUpCheckoutError(
                    "top-up order catalog snapshot is stale."
                )
            if order.state != "awaiting_payment":
                raise LemonSqueezyTopUpCheckoutError(
                    "top-up order is not awaiting payment."
                )

            if order.checkout_creation_status == "ready":
                if order.provider_variant_id != command.provider_variant_id:
                    raise LemonSqueezyTopUpCheckoutError(
                        "checkout replay conflicts with the bound variant."
                    )
                if not order.provider_checkout_id:
                    raise LemonSqueezyTopUpCheckoutError(
                        "ready checkout is missing provider checkout id."
                    )
                raise LemonSqueezyTopUpCheckoutError(
                    "checkout URL is not persisted and cannot be replayed safely."
                )
            if order.checkout_creation_status in {"creating", "uncertain"}:
                raise LemonSqueezyTopUpCheckoutError(
                    "checkout creation state is uncertain; manual reconciliation is required."
                )
            if order.checkout_creation_status != "not_started":
                raise LemonSqueezyTopUpCheckoutError(
                    "checkout creation state is invalid."
                )

            order.provider_variant_id = command.provider_variant_id
            order.checkout_creation_status = "creating"
            await uow.commit()

        try:
            response = await checkout_creator(
                LemonSqueezyCheckoutRequest(
                    store_id=command.store_id,
                    variant_id=command.provider_variant_id,
                    customer_ref=command.customer_ref,
                    order_ref=str(command.order_id),
                    subtotal_usd=Decimal(str(order.total_price_usd)),
                    email=command.email.strip() if command.email else None,
                    success_url=command.success_url,
                )
            )
        except Exception as exc:
            async with unit_of_work_factory() as uow:
                uncertain = await uow.top_up_orders.get_by_id(
                    command.order_id,
                    for_update=True,
                )
                if uncertain is not None and uncertain.checkout_creation_status == "creating":
                    uncertain.checkout_creation_status = "uncertain"
                    await uow.commit()
            raise LemonSqueezyTopUpCheckoutError(
                "payment provider checkout creation outcome is uncertain."
            ) from exc

        _validate_provider_response(response)

        async with unit_of_work_factory() as uow:
            order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
            if order is None:
                raise LemonSqueezyTopUpCheckoutError("top-up order disappeared after checkout.")
            if (
                order.customer_ref != command.customer_ref
                or order.provider_variant_id != command.provider_variant_id
                or order.checkout_creation_status != "creating"
            ):
                raise LemonSqueezyTopUpCheckoutError(
                    "top-up order changed while checkout was being created."
                )
            order.provider_checkout_id = response.checkout_id
            order.checkout_creation_status = "ready"
            await uow.commit()

        return CreateTopUpCheckoutResult(
            order_id=command.order_id,
            checkout_id=response.checkout_id,
            url=response.url,
            provider_variant_id=command.provider_variant_id,
            replayed=False,
            committed=True,
        )

    return create


def build_lemon_squeezy_checkout_payload(
    request: LemonSqueezyCheckoutRequest,
) -> dict[str, Any]:
    cents = _usd_to_cents(request.subtotal_usd)
    attributes: dict[str, Any] = {
        "checkout_options": {
            "embed": False,
            "media": False,
            "logo": True,
        },
        "checkout_data": {
            "custom": {
                "customer_ref": request.customer_ref,
                "order_ref": request.order_ref,
                "offer_ref": _TOP_UP_OFFER_REF,
            }
        },
        "product_options": {
            "redirect_url": request.success_url,
            "enabled_variants": [int(request.variant_id)],
        },
        "expires_at": None,
        "preview": False,
        "test_mode": False,
    }
    if request.email:
        attributes["checkout_data"]["email"] = request.email
    relationships = {
        "store": {"data": {"type": "stores", "id": request.store_id}},
        "variant": {"data": {"type": "variants", "id": request.variant_id}},
    }
    return {
        "data": {
            "type": "checkouts",
            "attributes": {
                **attributes,
                "custom_price": cents,
            },
            "relationships": relationships,
        }
    }


def lemon_squeezy_http_checkout_creator_factory(*, api_key: str):
    token = api_key.strip()
    if not token:
        raise ValueError("Lemon Squeezy API key is required.")

    async def create(request: LemonSqueezyCheckoutRequest) -> LemonSqueezyCheckoutResponse:
        import httpx

        payload = build_lemon_squeezy_checkout_payload(request)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.lemonsqueezy.com/v1/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.api+json",
                    "Content-Type": "application/vnd.api+json",
                },
            )
        if response.status_code not in {200, 201}:
            raise LemonSqueezyTopUpCheckoutError(
                "payment provider rejected checkout creation."
            )
        try:
            data = response.json()["data"]
            checkout_id = str(data["id"]).strip()
            url = str(data["attributes"]["url"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise LemonSqueezyTopUpCheckoutError(
                "payment provider checkout response is invalid."
            ) from exc
        return LemonSqueezyCheckoutResponse(checkout_id=checkout_id, url=url)

    return create


def _usd_to_cents(value: Decimal) -> int:
    normalized = Decimal(value).quantize(Decimal("0.01"))
    cents = normalized * 100
    if cents != cents.to_integral_value() or cents <= 0:
        raise LemonSqueezyTopUpCheckoutError("top-up checkout amount is invalid.")
    return int(cents)


def _validate(command: CreateTopUpCheckoutCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if not command.provider_variant_id.isdigit() or int(command.provider_variant_id) <= 0:
        raise ValueError("provider_variant_id must be a positive numeric identifier.")
    if not command.store_id.isdigit() or int(command.store_id) <= 0:
        raise ValueError("store_id must be a positive numeric identifier.")
    if not command.success_url.strip():
        raise ValueError("success_url must not be blank.")


def _validate_provider_response(response: LemonSqueezyCheckoutResponse) -> None:
    if not response.checkout_id.strip() or not response.checkout_id.isdigit():
        raise LemonSqueezyTopUpCheckoutError("provider checkout id is invalid.")
    if not response.url.startswith("https://"):
        raise LemonSqueezyTopUpCheckoutError("provider checkout URL is invalid.")


__all__ = [
    "CreateTopUpCheckoutCommand",
    "CreateTopUpCheckoutResult",
    "LemonSqueezyCheckoutRequest",
    "LemonSqueezyCheckoutResponse",
    "LemonSqueezyTopUpCheckoutError",
    "build_lemon_squeezy_checkout_payload",
    "create_lemon_squeezy_top_up_checkout_factory",
    "lemon_squeezy_http_checkout_creator_factory",
]
