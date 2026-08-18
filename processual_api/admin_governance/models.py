from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdministratorInvitation(Base):
    __tablename__ = "admin_governance_invitations"
    __table_args__ = (
        CheckConstraint(
            "supervision_level IN ('operations_supervisor', 'review_supervisor')",
            name="supervision_level_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')",
            name="status_allowed",
        ),
        Index(
            "ix_admin_governance_invitations_email_status",
            "email_normalized",
            "status",
            "expires_at",
        ),
        Index(
            "ix_admin_governance_invitations_inviter_created",
            "invited_by_user_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    supervision_level: Mapped[str] = mapped_column(String(40), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invite_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="SET NULL"),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="SET NULL"),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["AdministratorInvitation"]
