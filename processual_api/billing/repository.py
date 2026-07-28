"""Persistence operations for authoritative customer billing profiles."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.billing.models import CustomerBillingProfile


class BillingProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_context(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        for_update: bool = False,
    ) -> CustomerBillingProfile | None:
        statement = select(CustomerBillingProfile).where(
            CustomerBillingProfile.user_id == user_id,
        )

        if organization_id is None:
            statement = statement.where(
                CustomerBillingProfile.organization_id.is_(None),
            )
        else:
            statement = statement.where(
                CustomerBillingProfile.organization_id == organization_id,
            )

        if for_update:
            statement = statement.with_for_update()

        return await self._session.scalar(statement)

    async def upsert_for_context(
        self,
        *,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        country_code: str,
        region: str | None,
        city: str | None,
        postal_code: str | None,
        address_line_1: str | None,
        address_line_2: str | None,
    ) -> CustomerBillingProfile:
        profile = await self.get_for_context(
            user_id=user_id,
            organization_id=organization_id,
            for_update=True,
        )

        if profile is None:
            profile = CustomerBillingProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                organization_id=organization_id,
                country_code=country_code,
                region=region,
                city=city,
                postal_code=postal_code,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                status="active",
            )
            self._session.add(profile)
            await self._session.flush()
            return profile

        profile.country_code = country_code
        profile.region = region
        profile.city = city
        profile.postal_code = postal_code
        profile.address_line_1 = address_line_1
        profile.address_line_2 = address_line_2

        await self._session.flush()
        return profile
