"""SQLAlchemy storage model for the commercial event ledger.

Defining the schema model does not enable storage. Runtime event-ledger storage
remains fail-closed behind the commercial authority feature flags.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, Uuid, event, func
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class CommercialEventRecord(Base):
    __tablename__ = "commercial_events"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            name="uq_commercial_events_event_id",
        ),
        UniqueConstraint(
            "canonical_idempotency_key",
            name="uq_commercial_events_canonical_idempotency_key",
        ),
        Index(
            "ix_commercial_events_aggregate_sequence",
            "aggregate",
            "aggregate_id",
            "ledger_sequence",
        ),
    )

    ledger_sequence: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    aggregate: Mapped[str] = mapped_column(String(48), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    current_state: Mapped[str] = mapped_column(String(64), nullable=False)
    next_state: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    request_key: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_idempotency_key: Mapped[str] = mapped_column(String(900), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


@event.listens_for(CommercialEventRecord, "before_update")
def _reject_commercial_event_update(*_: object) -> None:
    raise ValueError("commercial event ledger records are append-only")


@event.listens_for(CommercialEventRecord, "before_delete")
def _reject_commercial_event_delete(*_: object) -> None:
    raise ValueError("commercial event ledger records are append-only")


__all__ = ["CommercialEventRecord"]
