from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)


class SqlAlchemyCommercialTopUpOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpOrder | None:
        statement = select(CommercialTopUpOrder).where(CommercialTopUpOrder.id == order_id)
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> CommercialTopUpOrder | None:
        return await self._session.scalar(
            select(CommercialTopUpOrder).where(CommercialTopUpOrder.idempotency_key == idempotency_key)
        )

    async def list_recovery_candidates(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[CommercialTopUpOrder]:
        statement = (
            select(CommercialTopUpOrder)
            .where(
                (CommercialTopUpOrder.checkout_creation_status == "uncertain")
                | (CommercialTopUpOrder.state == "payment_verified")
            )
            .order_by(CommercialTopUpOrder.created_at.asc(), CommercialTopUpOrder.id.asc())
            .limit(max(1, min(limit, 500)))
        )
        result = await self._session.scalars(statement)
        return tuple(result.all())

    def add(self, order: CommercialTopUpOrder) -> None:
        self._session.add(order)


class SqlAlchemyCommercialTopUpPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_order(
        self,
        order_id: uuid.UUID,
    ) -> CommercialTopUpPaymentEvidence | None:
        return await self._session.scalar(
            select(CommercialTopUpPaymentEvidence)
            .where(CommercialTopUpPaymentEvidence.order_id == order_id)
            .order_by(CommercialTopUpPaymentEvidence.created_at.desc())
            .limit(1)
        )

    async def get_by_provider_reference(
        self,
        provider_reference: str,
    ) -> CommercialTopUpPaymentEvidence | None:
        return await self._session.scalar(
            select(CommercialTopUpPaymentEvidence).where(
                CommercialTopUpPaymentEvidence.provider_reference == provider_reference
            )
        )

    def add(self, payment: CommercialTopUpPaymentEvidence) -> None:
        self._session.add(payment)


class SqlAlchemyCommercialTopUpGrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_order(
        self,
        order_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpGrant | None:
        statement = select(CommercialTopUpGrant).where(CommercialTopUpGrant.order_id == order_id)
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_idempotency_key(
        self,
        grant_idempotency_key: str,
    ) -> CommercialTopUpGrant | None:
        return await self._session.scalar(
            select(CommercialTopUpGrant).where(CommercialTopUpGrant.grant_idempotency_key == grant_idempotency_key)
        )

    def add(self, grant: CommercialTopUpGrant) -> None:
        self._session.add(grant)


class SqlAlchemyCommercialTopUpAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def append(self, record: CommercialTopUpAuditRecord) -> None:
        self._session.add(record)

    async def list_for_order(
        self,
        order_id: uuid.UUID,
    ) -> Sequence[CommercialTopUpAuditRecord]:
        result = await self._session.scalars(
            select(CommercialTopUpAuditRecord)
            .where(CommercialTopUpAuditRecord.order_id == order_id)
            .order_by(CommercialTopUpAuditRecord.occurred_at)
        )
        return result.all()
