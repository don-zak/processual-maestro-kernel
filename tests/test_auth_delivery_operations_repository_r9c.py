from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.auth.delivery_contracts import (
    DeliveryOperationalMetrics,
    DeliveryRedriveResult,
)
from processual_api.auth.delivery_repository import (
    SqlAlchemyDeliveryRepository,
)


class FakeResult:
    def __init__(self, row) -> None:
        self._row = row

    def one_or_none(self):
        return self._row

    def one(self):
        if self._row is None:
            raise AssertionError(
                "Expected exactly one repository result row."
            )
        return self._row


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSession:
    def __init__(self, rows) -> None:
        self._rows = list(rows)
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def begin(self):
        return FakeTransaction()

    async def execute(self, statement):
        self.statements.append(statement)

        if not self._rows:
            raise AssertionError(
                "Unexpected additional SQL execution."
            )

        return FakeResult(self._rows.pop(0))


def _repository(*rows):
    session = FakeSession(rows)

    return (
        SqlAlchemyDeliveryRepository(
            session_factory=lambda: session
        ),
        session,
    )


def _sql(statement) -> str:
    return " ".join(
        str(statement).lower().split()
    )


@pytest.mark.asyncio
async def test_redrive_dead_letter_is_guarded_and_maps_receipt():
    now = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )
    outbox_id = uuid.uuid4()

    repository, session = _repository(
        SimpleNamespace(
            id=outbox_id,
            available_at=now,
            attempt_count=8,
        )
    )

    result = await repository.redrive_dead_letter(
        outbox_id=outbox_id,
        available_at=now,
    )

    assert result == DeliveryRedriveResult(
        outbox_id=outbox_id,
        available_at=now,
        preserved_attempt_count=8,
    )
    assert len(session.statements) == 1

    statement_sql = _sql(session.statements[0])

    assert "update auth_delivery_outbox" in statement_sql
    assert "delivered_at is null" in statement_sql
    assert "dead_lettered_at is not null" in statement_sql
    assert "claim_id is null" in statement_sql
    assert "claimed_at is null" in statement_sql
    assert "returning" in statement_sql
    assert "attempt_count" in statement_sql


@pytest.mark.asyncio
async def test_redrive_returns_none_when_atomic_guard_rejects_row():
    now = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    repository, session = _repository(None)

    result = await repository.redrive_dead_letter(
        outbox_id=uuid.uuid4(),
        available_at=now,
    )

    assert result is None
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_redrive_rejects_naive_availability_clock():
    repository, session = _repository()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        await repository.redrive_dead_letter(
            outbox_id=uuid.uuid4(),
            available_at=datetime(
                2026,
                7,
                24,
                12,
                0,
            ),
        )

    assert session.statements == []


@pytest.mark.asyncio
async def test_operational_metrics_map_non_sensitive_counts():
    now = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    repository, session = _repository(
        SimpleNamespace(
            pending_count=4,
            retry_scheduled_count=3,
            leased_count=2,
            dead_letter_count=1,
            delivered_count=9,
            oldest_pending_created_at=datetime(
                2026,
                7,
                24,
                9,
                0,
                tzinfo=UTC,
            ),
        )
    )

    result = await repository.operational_metrics(
        now=now,
    )

    assert result == DeliveryOperationalMetrics(
        pending_count=4,
        retry_scheduled_count=3,
        leased_count=2,
        dead_letter_count=1,
        delivered_count=9,
        oldest_pending_age_seconds=10800,
    )
    assert len(session.statements) == 1

    statement_sql = _sql(session.statements[0])

    assert "auth_delivery_outbox" in statement_sql
    assert "delivered_at is null" in statement_sql
    assert "dead_lettered_at is null" in statement_sql
    assert "available_at <=" in statement_sql
    assert "available_at >" in statement_sql
    assert "claimed_at is null" in statement_sql
    assert "claimed_at is not null" in statement_sql
    assert "min(" in statement_sql


@pytest.mark.asyncio
async def test_operational_metrics_empty_outbox():
    now = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    repository, session = _repository(
        SimpleNamespace(
            pending_count=0,
            retry_scheduled_count=0,
            leased_count=0,
            dead_letter_count=0,
            delivered_count=0,
            oldest_pending_created_at=None,
        )
    )

    result = await repository.operational_metrics(
        now=now,
    )

    assert result == DeliveryOperationalMetrics(
        pending_count=0,
        retry_scheduled_count=0,
        leased_count=0,
        dead_letter_count=0,
        delivered_count=0,
        oldest_pending_age_seconds=None,
    )
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_operational_metrics_clamp_future_created_at_to_zero():
    now = datetime(
        2026,
        7,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    repository, _ = _repository(
        SimpleNamespace(
            pending_count=1,
            retry_scheduled_count=0,
            leased_count=0,
            dead_letter_count=0,
            delivered_count=0,
            oldest_pending_created_at=datetime(
                2026,
                7,
                24,
                12,
                5,
                tzinfo=UTC,
            ),
        )
    )

    result = await repository.operational_metrics(
        now=now,
    )

    assert result.oldest_pending_age_seconds == 0


@pytest.mark.asyncio
async def test_operational_metrics_reject_naive_clock():
    repository, session = _repository()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        await repository.operational_metrics(
            now=datetime(
                2026,
                7,
                24,
                12,
                0,
            ),
        )

    assert session.statements == []
