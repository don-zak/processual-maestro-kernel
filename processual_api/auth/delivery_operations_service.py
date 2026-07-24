from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from processual_api.auth.delivery_contracts import (
    DeliveryOperationalMetrics,
    DeliveryRedriveResult,
)


class DeliveryOperationsRepository(Protocol):
    async def redrive_dead_letter(
        self,
        *,
        outbox_id: uuid.UUID,
        available_at: datetime,
    ) -> DeliveryRedriveResult | None: ...

    async def operational_metrics(
        self,
        *,
        now: datetime,
    ) -> DeliveryOperationalMetrics: ...


class DeliveryRedriveUnavailableError(RuntimeError):
    """The requested dead-letter row cannot be redriven."""


class DeliveryOperationsService:
    def __init__(
        self,
        *,
        repository: DeliveryOperationsRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None:
            raise ValueError(
                "Delivery operations clock must be timezone-aware."
            )

        return now

    async def metrics(
        self,
    ) -> DeliveryOperationalMetrics:
        return await self._repository.operational_metrics(
            now=self._now(),
        )

    async def redrive(
        self,
        *,
        outbox_id: uuid.UUID,
    ) -> DeliveryRedriveResult:
        result = await self._repository.redrive_dead_letter(
            outbox_id=outbox_id,
            available_at=self._now(),
        )

        if result is None:
            raise DeliveryRedriveUnavailableError(
                "Dead-letter delivery is unavailable for redrive."
            )

        return result


__all__ = [
    "DeliveryOperationsRepository",
    "DeliveryOperationsService",
    "DeliveryRedriveUnavailableError",
]
