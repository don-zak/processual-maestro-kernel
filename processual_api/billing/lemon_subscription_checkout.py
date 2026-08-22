from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import AdminMarketOrder
from processual_api.billing.lemon_checkout_binding import (
    AdminMarketLemonCheckoutBinding,
)


class LemonSubscriptionCheckoutError(RuntimeError):
    """A subscription checkout cannot be created or rebound safely."""


@dataclass(frozen=True, slots=True)
class LemonSubscriptionCheckoutRequest:
    store_id: str
    variant_id: str
    customer_ref: str
    order_ref: str
    offer_ref: str
    country_code: str
    email: str | None
    success_url: str


@dataclass(frozen=True, slots=True)
class LemonSubscriptionCheckoutResponse:
    checkout_id: str
    url: str


class LemonSubscriptionCheckoutCreator(Protocol):
    async def __call__(
        self,
        request: LemonSubscriptionCheckoutRequest,
    ) -> LemonSubscriptionCheckoutResponse: ...


@dataclass(frozen=True, slots=True)
class CreateSubscriptionCheckoutCommand:
    order_id: uuid.UUID
    customer_ref: str
    offer_ref: str
    provider_variant_id: str
    store_id: str
    success_url: str
    email: str | None = None


@dataclass(frozen=True, slots=True)
class CreateSubscriptionCheckoutResult:
    order_id: uuid.UUID
    order_ref: str
    checkout_id: str
    url: str
    provider_variant_id: str
    committed: bool


def create_lemon_subscription_checkout_factory(
    *,
    session_factory: Callable[[], AsyncSession],
    checkout_creator: LemonSubscriptionCheckoutCreator,
):
    async def create(
        command: CreateSubscriptionCheckoutCommand,
    ) -> CreateSubscriptionCheckoutResult:
        _validate(command)

        async with session_factory() as session:
            async with session.begin():
                order = await session.scalar(
                    select(AdminMarketOrder)
                    .where(AdminMarketOrder.id == command.order_id)
                    .with_for_update()
                )
                if order is None:
                    raise LemonSubscriptionCheckoutError(
                        "checkout order was not found."
                    )
                _validate_order(order, command)

                binding = await session.scalar(
                    select(AdminMarketLemonCheckoutBinding)
                    .where(
                        AdminMarketLemonCheckoutBinding.order_id
                        == command.order_id
                    )
                    .with_for_update()
                )
                if binding is not None:
                    _validate_existing_binding(binding, command)
                    if binding.checkout_creation_status == "ready":
                        raise LemonSubscriptionCheckoutError(
                            "checkout already exists; do not create a duplicate."
                        )
                    if binding.checkout_creation_status in {
                        "creating",
                        "uncertain",
                    }:
                        raise LemonSubscriptionCheckoutError(
                            "checkout creation state is uncertain; reconciliation is required."
                        )
                    if binding.checkout_creation_status != "not_started":
                        raise LemonSubscriptionCheckoutError(
                            "checkout creation state is invalid."
                        )
                    binding.checkout_creation_status = "creating"
                    binding.updated_at = order.updated_at
                else:
                    binding = AdminMarketLemonCheckoutBinding(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        provider_variant_id=command.provider_variant_id,
                        provider_checkout_id=None,
                        checkout_creation_status="creating",
                        created_at=order.updated_at,
                        updated_at=order.updated_at,
                    )
                    session.add(binding)

                order_ref = order.order_ref
                country_code = order.country_code

        try:
            response = await checkout_creator(
                LemonSubscriptionCheckoutRequest(
                    store_id=command.store_id,
                    variant_id=command.provider_variant_id,
                    customer_ref=command.customer_ref,
                    order_ref=order_ref,
                    offer_ref=command.offer_ref,
                    country_code=country_code,
                    email=command.email.strip() if command.email else None,
                    success_url=command.success_url,
                )
            )
            _validate_provider_response(response)
        except Exception as exc:
            async with session_factory() as session:
                async with session.begin():
                    uncertain = await session.scalar(
                        select(AdminMarketLemonCheckoutBinding)
                        .where(
                            AdminMarketLemonCheckoutBinding.order_id
                            == command.order_id
                        )
                        .with_for_update()
                    )
                    if (
                        uncertain is not None
                        and uncertain.checkout_creation_status == "creating"
                    ):
                        uncertain.checkout_creation_status = "uncertain"
            raise LemonSubscriptionCheckoutError(
                "payment provider checkout creation outcome is uncertain."
            ) from exc

        async with session_factory() as session:
            async with session.begin():
                order = await session.scalar(
                    select(AdminMarketOrder)
                    .where(AdminMarketOrder.id == command.order_id)
                    .with_for_update()
                )
                binding = await session.scalar(
                    select(AdminMarketLemonCheckoutBinding)
                    .where(
                        AdminMarketLemonCheckoutBinding.order_id
                        == command.order_id
                    )
                    .with_for_update()
                )
                if order is None or binding is None:
                    raise LemonSubscriptionCheckoutError(
                        "checkout authority disappeared after provider creation."
                    )
                if (
                    order.customer_ref != command.customer_ref
                    or order.order_ref != order_ref
                    or binding.provider_variant_id
                    != command.provider_variant_id
                    or binding.checkout_creation_status != "creating"
                ):
                    raise LemonSubscriptionCheckoutError(
                        "checkout authority changed during provider creation."
                    )
                binding.provider_checkout_id = response.checkout_id
                binding.checkout_creation_status = "ready"

        return CreateSubscriptionCheckoutResult(
            order_id=command.order_id,
            order_ref=order_ref,
            checkout_id=response.checkout_id,
            url=response.url,
            provider_variant_id=command.provider_variant_id,
            committed=True,
        )

    return create


def build_lemon_subscription_checkout_payload(
    request: LemonSubscriptionCheckoutRequest,
) -> dict[str, Any]:
    checkout_data: dict[str, Any] = {
        "billing_address": {"country": request.country_code},
        "custom": {
            "customer_ref": request.customer_ref,
            "order_ref": request.order_ref,
            "offer_ref": request.offer_ref,
        },
    }
    if request.email:
        checkout_data["email"] = request.email

    return {
        "data": {
            "type": "checkouts",
            "attributes": {
                "product_options": {
                    "redirect_url": request.success_url,
                    "enabled_variants": [int(request.variant_id)],
                },
                "checkout_data": checkout_data,
                "expires_at": None,
                "preview": False,
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": request.store_id,
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": request.variant_id,
                    }
                },
            },
        }
    }


def lemon_subscription_http_checkout_creator_factory(*, api_key: str):
    token = api_key.strip()
    if not token:
        raise ValueError("Lemon Squeezy API key is required.")

    async def create(
        request: LemonSubscriptionCheckoutRequest,
    ) -> LemonSubscriptionCheckoutResponse:
        import httpx

        payload = build_lemon_subscription_checkout_payload(request)
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
            raise LemonSubscriptionCheckoutError(
                "payment provider rejected checkout creation."
            )
        try:
            data = response.json()["data"]
            checkout_id = str(data["id"]).strip()
            url = str(data["attributes"]["url"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise LemonSubscriptionCheckoutError(
                "payment provider checkout response is invalid."
            ) from exc
        return LemonSubscriptionCheckoutResponse(
            checkout_id=checkout_id,
            url=url,
        )

    return create


def _validate(command: CreateSubscriptionCheckoutCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if not command.offer_ref.strip():
        raise ValueError("offer_ref must not be blank.")
    if (
        not command.provider_variant_id.isdigit()
        or int(command.provider_variant_id) <= 0
    ):
        raise ValueError(
            "provider_variant_id must be a positive numeric identifier."
        )
    if not command.store_id.isdigit() or int(command.store_id) <= 0:
        raise ValueError("store_id must be a positive numeric identifier.")
    if not command.success_url.strip():
        raise ValueError("success_url must not be blank.")


def _validate_order(
    order: AdminMarketOrder,
    command: CreateSubscriptionCheckoutCommand,
) -> None:
    if order.customer_ref != command.customer_ref:
        raise LemonSubscriptionCheckoutError(
            "checkout customer conflicts with the internal order."
        )
    if order.selected_channel != "lemon_squeezy":
        raise LemonSubscriptionCheckoutError(
            "checkout order is not assigned to Lemon Squeezy."
        )
    if order.status != "awaiting_payment":
        raise LemonSubscriptionCheckoutError(
            "checkout order is not awaiting payment."
        )
    if order.payment_status != "pending":
        raise LemonSubscriptionCheckoutError(
            "checkout order payment state is not pending."
        )
    if (
        str(order.offer_snapshot.get("offer_ref", "")).strip().lower()
        != command.offer_ref.strip().lower()
    ):
        raise LemonSubscriptionCheckoutError(
            "checkout offer conflicts with the internal order."
        )


def _validate_existing_binding(
    binding: AdminMarketLemonCheckoutBinding,
    command: CreateSubscriptionCheckoutCommand,
) -> None:
    if binding.provider_variant_id != command.provider_variant_id:
        raise LemonSubscriptionCheckoutError(
            "checkout replay conflicts with the bound variant."
        )
    if (
        binding.checkout_creation_status == "ready"
        and not binding.provider_checkout_id
    ):
        raise LemonSubscriptionCheckoutError(
            "ready checkout is missing provider checkout id."
        )


def _validate_provider_response(
    response: LemonSubscriptionCheckoutResponse,
) -> None:
    try:
        uuid.UUID(response.checkout_id)
    except (ValueError, AttributeError) as exc:
        raise LemonSubscriptionCheckoutError(
            "provider checkout id is invalid."
        ) from exc
    if not response.url.startswith("https://"):
        raise LemonSubscriptionCheckoutError(
            "provider checkout URL is invalid."
        )


__all__ = [
    "CreateSubscriptionCheckoutCommand",
    "CreateSubscriptionCheckoutResult",
    "LemonSubscriptionCheckoutError",
    "LemonSubscriptionCheckoutRequest",
    "LemonSubscriptionCheckoutResponse",
    "build_lemon_subscription_checkout_payload",
    "create_lemon_subscription_checkout_factory",
    "lemon_subscription_http_checkout_creator_factory",
]
