from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketAssessmentCommercialTerms(Base):
    __tablename__ = "admin_market_assessment_commercial_terms"
    __table_args__ = (
        CheckConstraint("amount_minor_units >= 0", name="amount_nonnegative"),
        CheckConstraint("price_source IN ('assessment', 'contract')", name="price_source_allowed"),
        CheckConstraint("length(currency) = 3", name="currency_length"),
        CheckConstraint(
            "billing_interval IN ('monthly', 'annual', 'one_time', 'custom')",
            name="billing_interval_allowed",
        ),
        CheckConstraint("length(payload_digest) = 64", name="payload_digest_length"),
        UniqueConstraint(
            "assessment_binding_hash",
            name="uq_admin_market_assessment_commercial_terms_binding_hash",
        ),
        UniqueConstraint(
            "approval_reference",
            name="uq_admin_market_assessment_commercial_terms_approval_reference",
        ),
        Index(
            "ix_admin_market_assessment_commercial_terms_customer",
            "customer_ref",
            "public_plan_id",
        ),
    )

    terms_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_binding_hash: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "admin_market_assessment_quota_profiles.assessment_binding_hash",
            name="fk_admin_market_assessment_terms_binding_hash",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    assessment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    public_plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    terms_version: Mapped[str] = mapped_column(String(64), nullable=False)
    price_source: Mapped[str] = mapped_column(String(24), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(24), nullable=False)
    amount_minor_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemyAssessmentCommercialTermsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_terms_ref(
        self,
        terms_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None:
        statement = select(AdminMarketAssessmentCommercialTerms).where(
            AdminMarketAssessmentCommercialTerms.terms_ref == terms_ref
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_binding_hash(
        self,
        assessment_binding_hash: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None:
        statement = select(AdminMarketAssessmentCommercialTerms).where(
            AdminMarketAssessmentCommercialTerms.assessment_binding_hash
            == assessment_binding_hash
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_approval_reference(
        self,
        approval_reference: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentCommercialTerms | None:
        statement = select(AdminMarketAssessmentCommercialTerms).where(
            AdminMarketAssessmentCommercialTerms.approval_reference
            == approval_reference
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, terms: AdminMarketAssessmentCommercialTerms) -> None:
        self._session.add(terms)


__all__ = [
    "AdminMarketAssessmentCommercialTerms",
    "SqlAlchemyAssessmentCommercialTermsRepository",
]
