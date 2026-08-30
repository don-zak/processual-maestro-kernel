from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketOfferProviderBinding(Base):
    __tablename__ = "admin_market_offer_provider_bindings"
    __table_args__ = (
        CheckConstraint(
            "provider = 'lemon_squeezy'",
            name="provider_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'verified', 'revoked')",
            name="status_allowed",
        ),
        CheckConstraint(
            """
            (status = 'pending' AND verification_reference IS NULL AND verified_at IS NULL)
            OR
            (status IN ('verified', 'revoked') AND verification_reference IS NOT NULL AND verified_at IS NOT NULL)
            """,
            name="verification_state_consistent",
        ),
        UniqueConstraint(
            "offer_id",
            name="uq_admin_market_offer_provider_binding_offer",
        ),
        UniqueConstraint(
            "provider_variant_id",
            name="uq_admin_market_offer_provider_binding_variant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admin_market_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="lemon_squeezy",
    )
    provider_variant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    verification_reference: Mapped[str | None] = mapped_column(String(128))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class SqlAlchemyOfferProviderBindingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_offer_id(
        self,
        offer_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOfferProviderBinding | None:
        statement = select(AdminMarketOfferProviderBinding).where(
            AdminMarketOfferProviderBinding.offer_id == offer_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, binding: AdminMarketOfferProviderBinding) -> None:
        self._session.add(binding)


__all__ = [
    "AdminMarketOfferProviderBinding",
    "SqlAlchemyOfferProviderBindingRepository",
]
