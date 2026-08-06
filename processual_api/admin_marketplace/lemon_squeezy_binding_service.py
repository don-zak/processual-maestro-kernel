from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemonSqueezyCustomerBinding,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConcurrencyError,
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)


class LemonSqueezyBindingConflictError(RuntimeError):
    """Requested provider binding conflicts with authoritative ownership."""


@dataclass(frozen=True, slots=True)
class LemonSqueezyBindingCommand:
    customer_ref: str
    order_id: uuid.UUID
    offer_id: uuid.UUID
    provider_customer_id: str
    provider_order_id: str
    provider_subscription_id: str | None
    variant_id: str
    currency: str
    total_amount: str
    subscription_id: uuid.UUID | None = None
    provider_effective_at: datetime | None = None


def bind_lemon_squeezy_order_factory(
    *,
    unit_of_work_factory: Callable[[], SqlAlchemyAdminMarketplaceUnitOfWork],
):
    async def bind(command: LemonSqueezyBindingCommand) -> AdminMarketLemonSqueezyBinding:
        _validate_command(command)
        try:
            async with unit_of_work_factory() as uow:
                customer_owner = await uow.lemon_squeezy_bindings.get_customer_binding_by_customer_ref(
                    command.customer_ref,
                    for_update=True,
                )
                provider_owner = await uow.lemon_squeezy_bindings.get_customer_binding_by_provider_customer_id(
                    command.provider_customer_id,
                    for_update=True,
                )
                _assert_owner_compatible(command, customer_owner, provider_owner)

                if customer_owner is None:
                    customer_owner = AdminMarketLemonSqueezyCustomerBinding(
                        customer_ref=command.customer_ref,
                        provider_customer_id=command.provider_customer_id,
                    )
                    uow.lemon_squeezy_bindings.add_customer_binding(customer_owner)

                existing = await uow.lemon_squeezy_bindings.get_by_order_id(
                    command.order_id,
                    for_update=True,
                )
                if existing is not None:
                    _assert_binding_matches(command, existing)
                    return existing

                binding = AdminMarketLemonSqueezyBinding(
                    customer_ref=command.customer_ref,
                    order_id=command.order_id,
                    offer_id=command.offer_id,
                    subscription_id=command.subscription_id,
                    provider_customer_id=command.provider_customer_id,
                    provider_order_id=command.provider_order_id,
                    provider_subscription_id=command.provider_subscription_id,
                    variant_id=command.variant_id,
                    currency=command.currency.upper(),
                    total_amount=command.total_amount,
                    last_provider_effective_at=command.provider_effective_at,
                )
                uow.lemon_squeezy_bindings.add(binding)
                await uow.commit()
                return binding
        except AdminMarketplaceConcurrencyError:
            raise
        except AdminMarketplaceConflictError as exc:
            raise LemonSqueezyBindingConflictError(
                "Lemon Squeezy binding conflicts with existing ownership."
            ) from exc

    return bind


def _validate_command(command: LemonSqueezyBindingCommand) -> None:
    values = (
        command.customer_ref,
        command.provider_customer_id,
        command.provider_order_id,
        command.variant_id,
        command.currency,
        command.total_amount,
    )
    if any(not value.strip() for value in values):
        raise ValueError("Lemon Squeezy binding command is incomplete.")
    if len(command.currency.strip()) != 3:
        raise ValueError("Lemon Squeezy binding currency is invalid.")


def _assert_owner_compatible(
    command: LemonSqueezyBindingCommand,
    customer_owner: AdminMarketLemonSqueezyCustomerBinding | None,
    provider_owner: AdminMarketLemonSqueezyCustomerBinding | None,
) -> None:
    if customer_owner is not None and (
        customer_owner.provider_customer_id != command.provider_customer_id
    ):
        raise LemonSqueezyBindingConflictError(
            "Internal customer already belongs to another provider customer."
        )
    if provider_owner is not None and provider_owner.customer_ref != command.customer_ref:
        raise LemonSqueezyBindingConflictError(
            "Provider customer already belongs to another internal customer."
        )


def _assert_binding_matches(
    command: LemonSqueezyBindingCommand,
    binding: AdminMarketLemonSqueezyBinding,
) -> None:
    expected = (
        command.customer_ref,
        command.offer_id,
        command.subscription_id,
        command.provider_customer_id,
        command.provider_order_id,
        command.provider_subscription_id,
        command.variant_id,
        command.currency.upper(),
        command.total_amount,
    )
    actual = (
        binding.customer_ref,
        binding.offer_id,
        binding.subscription_id,
        binding.provider_customer_id,
        binding.provider_order_id,
        binding.provider_subscription_id,
        binding.variant_id,
        binding.currency,
        binding.total_amount,
    )
    if actual != expected:
        raise LemonSqueezyBindingConflictError(
            "Order already has a different Lemon Squeezy binding."
        )


__all__ = [
    "LemonSqueezyBindingCommand",
    "LemonSqueezyBindingConflictError",
    "bind_lemon_squeezy_order_factory",
]
