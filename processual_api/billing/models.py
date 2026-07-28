"""PostgreSQL models for authoritative customer billing profiles."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class CustomerBillingProfile(Base):
    """Authoritative billing address used to resolve public checkout channels."""

    __tablename__ = "customer_billing_profiles"
    __table_args__ = (
        CheckConstraint(
            "country_code = upper(country_code) AND length(country_code) = 2",
            name="country_code_format",
        ),
        CheckConstraint(
            "status IN ('active', 'review_required', 'disabled')",
            name="status_allowed",
        ),
        Index(
            "uq_customer_billing_profiles_personal",
            "user_id",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        Index(
            "uq_customer_billing_profiles_organization",
            "user_id",
            "organization_id",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
        Index(
            "ix_customer_billing_profiles_country_status",
            "country_code",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("identity_organizations.id", ondelete="SET NULL"),
    )
    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )
    region: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(160))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    address_line_1: Mapped[str | None] = mapped_column(String(300))
    address_line_2: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )
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
