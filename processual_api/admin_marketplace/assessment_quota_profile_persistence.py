from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.db.base import Base


class AdminMarketAssessmentQuotaProfile(Base):
    __tablename__ = "admin_market_assessment_quota_profiles"
    __table_args__ = (
        CheckConstraint("limit_units > 0", name="limit_units_positive"),
        CheckConstraint("cycle_kind = 'calendar_month'", name="cycle_kind_calendar_month"),
        CheckConstraint("compatibility_period_days = 30", name="compatibility_period_days_monthly"),
        CheckConstraint(
            "length(assessment_binding_hash) = 64 AND length(payload_digest) = 64",
            name="digests_length",
        ),
        UniqueConstraint(
            "assessment_binding_hash",
            name="uq_admin_market_assessment_quota_binding_hash",
        ),
    )

    profile_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    public_plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_source_plan_code: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(128), nullable=False)
    limit_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cycle_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    compatibility_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_version: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SqlAlchemyAssessmentQuotaProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_profile_ref(
        self,
        profile_ref: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketAssessmentQuotaProfile | None:
        statement = select(AdminMarketAssessmentQuotaProfile).where(
            AdminMarketAssessmentQuotaProfile.profile_ref == profile_ref
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    def add(self, profile: AdminMarketAssessmentQuotaProfile) -> None:
        self._session.add(profile)


__all__ = [
    "AdminMarketAssessmentQuotaProfile",
    "SqlAlchemyAssessmentQuotaProfileRepository",
]
