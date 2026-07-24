from __future__ import annotations

from dataclasses import dataclass

from processual_api.auth.delivery_operations_service import (
    DeliveryOperationsService,
)
from processual_api.auth.delivery_repository import (
    SqlAlchemyDeliveryRepository,
)
from processual_api.db.session import get_session_factory


class DeliveryOperationsRuntimeUnavailableError(RuntimeError):
    """Delivery operations runtime authority is unavailable."""


@dataclass(frozen=True, slots=True)
class DeliveryOperationsRuntime:
    service: DeliveryOperationsService


async def build_delivery_operations_runtime(
) -> DeliveryOperationsRuntime:
    try:
        session_factory = get_session_factory()
        repository = SqlAlchemyDeliveryRepository(
            session_factory,
        )
    except (RuntimeError, ValueError) as exc:
        raise DeliveryOperationsRuntimeUnavailableError(
            "Delivery operations authority is unavailable."
        ) from exc

    return DeliveryOperationsRuntime(
        service=DeliveryOperationsService(
            repository=repository,
        ),
    )


__all__ = [
    "DeliveryOperationsRuntime",
    "DeliveryOperationsRuntimeUnavailableError",
    "build_delivery_operations_runtime",
]
