from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from processual_api.auth.delivery_contracts import (
    DeliveryOperationalMetrics,
    DeliveryRedriveResult,
)
from processual_api.auth.delivery_operations_service import (
    DeliveryOperationsService,
    DeliveryRedriveUnavailableError,
)


class FakeDeliveryOperationsRepository:
    def __init__(
        self,
        *,
        metrics_result: DeliveryOperationalMetrics | None = None,
        redrive_result: DeliveryRedriveResult | None = None,
    ) -> None:
        self.metrics_result = metrics_result
        self.redrive_result = redrive_result
        self.metrics_calls: list[datetime] = []
        self.redrive_calls: list[tuple[uuid.UUID, datetime]] = []

    async def operational_metrics(
        self,
        *,
        now: datetime,
    ) -> DeliveryOperationalMetrics:
        self.metrics_calls.append(now)

        if self.metrics_result is None:
            raise AssertionError(
                "Metrics result was not configured."
            )

        return self.metrics_result

    async def redrive_dead_letter(
        self,
        *,
        outbox_id: uuid.UUID,
        available_at: datetime,
    ) -> DeliveryRedriveResult | None:
        self.redrive_calls.append(
            (
                outbox_id,
                available_at,
            )
        )

        return self.redrive_result


@pytest.mark.asyncio
async def test_metrics_uses_authoritative_service_clock():
    now = datetime(
        2026,
        7,
        24,
        14,
        0,
        tzinfo=UTC,
    )
    expected = DeliveryOperationalMetrics(
        pending_count=4,
        retry_scheduled_count=3,
        leased_count=2,
        dead_letter_count=1,
        delivered_count=9,
        oldest_pending_age_seconds=120,
    )
    repository = FakeDeliveryOperationsRepository(
        metrics_result=expected,
    )
    service = DeliveryOperationsService(
        repository=repository,
        clock=lambda: now,
    )

    result = await service.metrics()

    assert result == expected
    assert repository.metrics_calls == [now]
    assert repository.redrive_calls == []


@pytest.mark.asyncio
async def test_redrive_maps_repository_receipt():
    now = datetime(
        2026,
        7,
        24,
        14,
        0,
        tzinfo=UTC,
    )
    outbox_id = uuid.uuid4()
    expected = DeliveryRedriveResult(
        outbox_id=outbox_id,
        available_at=now,
        preserved_attempt_count=8,
    )
    repository = FakeDeliveryOperationsRepository(
        redrive_result=expected,
    )
    service = DeliveryOperationsService(
        repository=repository,
        clock=lambda: now,
    )

    result = await service.redrive(
        outbox_id=outbox_id,
    )

    assert result == expected
    assert repository.redrive_calls == [
        (
            outbox_id,
            now,
        )
    ]


@pytest.mark.asyncio
async def test_redrive_rejects_unavailable_row():
    now = datetime(
        2026,
        7,
        24,
        14,
        0,
        tzinfo=UTC,
    )
    outbox_id = uuid.uuid4()
    repository = FakeDeliveryOperationsRepository(
        redrive_result=None,
    )
    service = DeliveryOperationsService(
        repository=repository,
        clock=lambda: now,
    )

    with pytest.raises(
        DeliveryRedriveUnavailableError,
        match="unavailable",
    ):
        await service.redrive(
            outbox_id=outbox_id,
        )

    assert repository.redrive_calls == [
        (
            outbox_id,
            now,
        )
    ]


@pytest.mark.asyncio
async def test_metrics_rejects_naive_service_clock():
    repository = FakeDeliveryOperationsRepository(
        metrics_result=DeliveryOperationalMetrics(
            pending_count=0,
            retry_scheduled_count=0,
            leased_count=0,
            dead_letter_count=0,
            delivered_count=0,
            oldest_pending_age_seconds=None,
        )
    )
    service = DeliveryOperationsService(
        repository=repository,
        clock=lambda: datetime(
            2026,
            7,
            24,
            14,
            0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        await service.metrics()

    assert repository.metrics_calls == []


@pytest.mark.asyncio
async def test_redrive_rejects_naive_service_clock():
    repository = FakeDeliveryOperationsRepository()
    service = DeliveryOperationsService(
        repository=repository,
        clock=lambda: datetime(
            2026,
            7,
            24,
            14,
            0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        await service.redrive(
            outbox_id=uuid.uuid4(),
        )

    assert repository.redrive_calls == []
