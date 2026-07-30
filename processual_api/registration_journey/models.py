from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class RegistrationIntentRow(Base):
    __tablename__ = "registration_intents"
    __table_args__ = (
        CheckConstraint("version >= 0", name="version_nonnegative"),
        CheckConstraint(
            "state IN ('plan_selected','registration_pending','email_verification_pending','profile_pending')",
            name="state_allowed",
        ),
        UniqueConstraint("session_binding_hash", "plan_id", name="uq_registration_intent_session_plan"),
        Index("ix_registration_intents_expiry_state", "expires_at", "state"),
    )

    intent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_context: Mapped[str] = mapped_column(String(64), nullable=False)
    billing_cycle: Mapped[str | None] = mapped_column(String(16))
    account_type: Mapped[str | None] = mapped_column(String(24))
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    session_binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("identity_users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class JourneyCheckpointRow(Base):
    __tablename__ = "registration_journey_checkpoints"
    __table_args__ = (
        CheckConstraint("state_version >= 0", name="state_version_nonnegative"),
        UniqueConstraint("intent_id", name="uq_registration_journey_checkpoint_intent"),
    )

    checkpoint_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    intent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("registration_intents.intent_id", ondelete="CASCADE"),
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(String(32), nullable=False)
    recovery_action: Mapped[str] = mapped_column(String(128), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
