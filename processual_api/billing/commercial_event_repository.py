"""SQLAlchemy adapter for the append-only commercial event ledger."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_event_contracts import (
    CommercialEvent,
    CommercialIdempotencyKey,
)
from processual_api.billing.commercial_event_models import CommercialEventRecord
from processual_api.billing.commercial_state_machine import CommercialAggregate


class SqlAlchemyCommercialEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_idempotency_key(
        self,
        canonical_key: str,
    ) -> CommercialEvent | None:
        record = await self._session.scalar(
            select(CommercialEventRecord).where(
                CommercialEventRecord.canonical_idempotency_key == canonical_key
            )
        )
        return _to_event(record) if record is not None else None

    def append(self, event: CommercialEvent) -> None:
        self._session.add(_to_record(event))

    async def list_for_aggregate(
        self,
        aggregate: CommercialAggregate,
        aggregate_id,
    ) -> tuple[CommercialEvent, ...]:
        result = await self._session.scalars(
            select(CommercialEventRecord)
            .where(
                CommercialEventRecord.aggregate == aggregate.value,
                CommercialEventRecord.aggregate_id == aggregate_id,
            )
            .order_by(
                CommercialEventRecord.occurred_at.asc(),
                CommercialEventRecord.event_id.asc(),
            )
        )
        records: Sequence[CommercialEventRecord] = result.all()
        return tuple(_to_event(record) for record in records)


def _to_record(event: CommercialEvent) -> CommercialEventRecord:
    return CommercialEventRecord(
        event_id=event.event_id,
        aggregate=event.aggregate.value,
        aggregate_id=event.aggregate_id,
        current_state=event.current_state,
        next_state=event.next_state,
        operation=event.operation,
        request_key=event.idempotency_key.request_key,
        canonical_idempotency_key=event.idempotency_key.canonical,
        occurred_at=event.occurred_at,
        actor_reference=event.actor_reference,
        evidence_reference=event.evidence_reference,
        payload_digest=event.payload_digest,
    )


def _to_event(record: CommercialEventRecord) -> CommercialEvent:
    aggregate = CommercialAggregate(record.aggregate)
    return CommercialEvent(
        event_id=record.event_id,
        aggregate=aggregate,
        aggregate_id=record.aggregate_id,
        current_state=record.current_state,
        next_state=record.next_state,
        operation=record.operation,
        idempotency_key=CommercialIdempotencyKey(
            aggregate=aggregate,
            aggregate_id=record.aggregate_id,
            operation=record.operation,
            request_key=record.request_key,
        ),
        occurred_at=record.occurred_at,
        actor_reference=record.actor_reference,
        evidence_reference=record.evidence_reference,
        payload_digest=record.payload_digest,
    )


__all__ = ["SqlAlchemyCommercialEventRepository"]
