from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_CATALOG_VERSION

_TOP_UP_OFFER_REF = "quota_top_up"


class LemonSqueezyTopUpCheckoutRecoveryError(RuntimeError):
    """An uncertain provider checkout cannot be rebound safely."""


@dataclass(frozen=True, slots=True)
class LemonSqueezyCheckoutCandidate:
    checkout_id: str
    url: str
    store_id: str
    variant_id: str
    custom_price: int
    custom_data: dict[str, object]


class LemonSqueezyCheckoutFinder(Protocol):
    async def __call__(
        self,
        *,
        store_id: str,
        variant_id: str,
    ) -> tuple[LemonSqueezyCheckoutCandidate, ...]: ...


@dataclass(frozen=True, slots=True)
class RecoverTopUpCheckoutCommand:
    order_id: uuid.UUID
    customer_ref: str
    store_id: str
    provider_variant_id: str


@dataclass(frozen=True, slots=True)
class RecoverTopUpCheckoutResult:
    order_id: uuid.UUID
    checkout_id: str
    url: str
    recovered: bool
    committed: bool


def recover_lemon_squeezy_top_up_checkout_factory(
    *,
    unit_of_work_factory: Callable[[], object],
    checkout_finder: LemonSqueezyCheckoutFinder,
):
    async def recover(command: RecoverTopUpCheckoutCommand) -> RecoverTopUpCheckoutResult:
        _validate_command(command)

        async with unit_of_work_factory() as uow:
            order = await uow.top_up_orders.get_by_id(command.order_id, for_update=False)
            if order is None:
                raise LemonSqueezyTopUpCheckoutRecoveryError("top-up order was not found.")
            _validate_order(command=command, order=order)
            if order.checkout_creation_status == "ready":
                if not order.provider_checkout_id:
                    raise LemonSqueezyTopUpCheckoutRecoveryError(
                        "ready top-up checkout is missing provider checkout id."
                    )
                return RecoverTopUpCheckoutResult(
                    order_id=order.id,
                    checkout_id=order.provider_checkout_id,
                    url="",
                    recovered=False,
                    committed=False,
                )
            if order.checkout_creation_status not in {"creating", "uncertain"}:
                raise LemonSqueezyTopUpCheckoutRecoveryError(
                    "top-up checkout is not eligible for recovery."
                )
            expected_cents = _usd_to_cents(Decimal(str(order.total_price_usd)))

        candidates = await checkout_finder(
            store_id=command.store_id,
            variant_id=command.provider_variant_id,
        )
        matches = tuple(
            candidate
            for candidate in candidates
            if _candidate_matches(
                candidate=candidate,
                command=command,
                expected_cents=expected_cents,
            )
        )
        if len(matches) != 1:
            raise LemonSqueezyTopUpCheckoutRecoveryError(
                "provider checkout recovery requires exactly one authoritative match."
            )
        match = matches[0]
        _validate_candidate_identity(match)

        async with unit_of_work_factory() as uow:
            order = await uow.top_up_orders.get_by_id(command.order_id, for_update=True)
            if order is None:
                raise LemonSqueezyTopUpCheckoutRecoveryError(
                    "top-up order disappeared during recovery."
                )
            _validate_order(command=command, order=order)
            if order.checkout_creation_status == "ready":
                if order.provider_checkout_id != match.checkout_id:
                    raise LemonSqueezyTopUpCheckoutRecoveryError(
                        "top-up checkout was rebound to a different provider checkout."
                    )
                return RecoverTopUpCheckoutResult(
                    order_id=order.id,
                    checkout_id=match.checkout_id,
                    url=match.url,
                    recovered=False,
                    committed=False,
                )
            if order.checkout_creation_status not in {"creating", "uncertain"}:
                raise LemonSqueezyTopUpCheckoutRecoveryError(
                    "top-up checkout state changed during recovery."
                )
            order.provider_checkout_id = match.checkout_id
            order.checkout_creation_status = "ready"
            await uow.commit()

        return RecoverTopUpCheckoutResult(
            order_id=command.order_id,
            checkout_id=match.checkout_id,
            url=match.url,
            recovered=True,
            committed=True,
        )

    return recover


def lemon_squeezy_http_checkout_finder_factory(*, api_key: str):
    token = api_key.strip()
    if not token:
        raise ValueError("Lemon Squeezy API key is required.")

    async def find(
        *,
        store_id: str,
        variant_id: str,
    ) -> tuple[LemonSqueezyCheckoutCandidate, ...]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    "https://api.lemonsqueezy.com/v1/checkouts",
                    params={
                        "filter[store_id]": store_id,
                        "filter[variant_id]": variant_id,
                        "page[size]": "100",
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.api+json",
                        "Content-Type": "application/vnd.api+json",
                    },
                )
        except httpx.HTTPError as exc:
            raise LemonSqueezyTopUpCheckoutRecoveryError(
                "payment provider checkout recovery request failed."
            ) from exc
        if response.status_code != 200:
            raise LemonSqueezyTopUpCheckoutRecoveryError(
                "payment provider checkout recovery request failed."
            )
        try:
            data = response.json()["data"]
            if not isinstance(data, list):
                raise TypeError("checkout list response must contain a list")
            return tuple(_candidate_from_provider(item) for item in data)
        except (KeyError, TypeError, ValueError) as exc:
            raise LemonSqueezyTopUpCheckoutRecoveryError(
                "payment provider checkout recovery response is invalid."
            ) from exc

    return find


def _candidate_from_provider(item: dict[str, Any]) -> LemonSqueezyCheckoutCandidate:
    attributes = item["attributes"]
    checkout_data = attributes.get("checkout_data") or {}
    custom_data = checkout_data.get("custom") or {}
    if not isinstance(custom_data, dict):
        raise TypeError("checkout custom data must be an object")
    return LemonSqueezyCheckoutCandidate(
        checkout_id=str(item["id"]).strip(),
        url=str(attributes["url"]).strip(),
        store_id=str(attributes["store_id"]).strip(),
        variant_id=str(attributes["variant_id"]).strip(),
        custom_price=int(attributes["custom_price"]),
        custom_data=custom_data,
    )


def _candidate_matches(
    *,
    candidate: LemonSqueezyCheckoutCandidate,
    command: RecoverTopUpCheckoutCommand,
    expected_cents: int,
) -> bool:
    custom = candidate.custom_data
    return (
        candidate.store_id == command.store_id
        and candidate.variant_id == command.provider_variant_id
        and candidate.custom_price == expected_cents
        and str(custom.get("customer_ref") or "") == command.customer_ref
        and str(custom.get("order_ref") or "") == str(command.order_id)
        and str(custom.get("offer_ref") or "") == _TOP_UP_OFFER_REF
    )


def _validate_candidate_identity(candidate: LemonSqueezyCheckoutCandidate) -> None:
    try:
        uuid.UUID(candidate.checkout_id)
    except (ValueError, AttributeError) as exc:
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "recovered provider checkout id is invalid."
        ) from exc
    if not candidate.url.startswith("https://"):
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "recovered provider checkout URL is invalid."
        )


def _validate_order(*, command: RecoverTopUpCheckoutCommand, order: object) -> None:
    if order.customer_ref != command.customer_ref:
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "top-up checkout customer conflicts with the order."
        )
    if order.channel != "lemon_squeezy" or order.state != "awaiting_payment":
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "top-up order is not recoverable through Lemon Squeezy."
        )
    if order.plan_catalog_version != PLAN_FULFILLMENT_CATALOG_VERSION:
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "top-up order catalog snapshot is stale."
        )
    if order.provider_variant_id != command.provider_variant_id:
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "top-up checkout variant conflicts with the order."
        )


def _validate_command(command: RecoverTopUpCheckoutCommand) -> None:
    if not command.customer_ref.strip():
        raise ValueError("customer_ref must not be blank.")
    if not command.store_id.isdigit() or int(command.store_id) <= 0:
        raise ValueError("store_id must be a positive numeric identifier.")
    if not command.provider_variant_id.isdigit() or int(command.provider_variant_id) <= 0:
        raise ValueError("provider_variant_id must be a positive numeric identifier.")


def _usd_to_cents(value: Decimal) -> int:
    normalized = Decimal(value).quantize(Decimal("0.01"))
    cents = normalized * 100
    if cents != cents.to_integral_value() or cents <= 0:
        raise LemonSqueezyTopUpCheckoutRecoveryError(
            "top-up checkout amount is invalid."
        )
    return int(cents)


__all__ = [
    "LemonSqueezyCheckoutCandidate",
    "LemonSqueezyTopUpCheckoutRecoveryError",
    "RecoverTopUpCheckoutCommand",
    "RecoverTopUpCheckoutResult",
    "lemon_squeezy_http_checkout_finder_factory",
    "recover_lemon_squeezy_top_up_checkout_factory",
]
