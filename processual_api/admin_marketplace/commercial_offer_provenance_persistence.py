from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
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


class AdminMarketOfferProvenance(Base):
    __tablename__ = "admin_market_offer_provenance"
    __table_args__ = (
        UniqueConstraint(
            "offer_id",
            name="uq_admin_market_offer_provenance_offer_id",
        ),
        UniqueConstraint(
            "evidence_sha256",
            name="uq_admin_market_offer_provenance_digest",
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
    provenance_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_pricing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_pricebook_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemyOfferProvenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_offer_id(
        self,
        offer_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketOfferProvenance | None:
        statement = select(AdminMarketOfferProvenance).where(
            AdminMarketOfferProvenance.offer_id == offer_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, provenance: AdminMarketOfferProvenance) -> None:
        self._session.add(provenance)


__all__ = [
    "AdminMarketOfferProvenance",
    "SqlAlchemyOfferProvenanceRepository",
]
