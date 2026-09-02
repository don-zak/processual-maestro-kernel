"""SQLAlchemy metadata for the shared External Evaluation delivery ledger."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class EvaluationRuntimeDelivery(Base):
    """Shared idempotency authority for bounded external Evaluation execution."""

    __tablename__ = "evaluation_runtime_delivery"

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    owner_id_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    grant_id: Mapped[str] = mapped_column(String(160), nullable=False)
    api_key_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(160), nullable=False)
    binding_id: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    state_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    replay_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    execution_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_persisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(200))
    network_outcome: Mapped[str | None] = mapped_column(String(40))
    raw_task_input_persisted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    raw_secret_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    __table_args__ = (
        UniqueConstraint(
            "owner_id_sha256",
            "grant_id",
            "api_key_id",
            "idempotency_key_sha256",
            name="uq_evaluation_runtime_delivery_authority_key",
        ),
        CheckConstraint(
            "state IN ('executing', 'evidence_persisted', 'failed')",
            name="state",
        ),
        Index(
            "ix_evaluation_runtime_delivery_owner_state",
            "owner_id_sha256",
            "state",
        ),
    )


__all__ = ["EvaluationRuntimeDelivery"]
