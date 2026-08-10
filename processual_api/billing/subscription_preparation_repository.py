from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import AuthRegistrationPlanIntent


class SqlAlchemySubscriptionPreparationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def registration_plan_intent_for_user(
        self,
        *,
        user_id: uuid.UUID,
    ) -> AuthRegistrationPlanIntent | None:
        return await self._session.scalar(
            select(AuthRegistrationPlanIntent).where(
                AuthRegistrationPlanIntent.user_id == user_id
            )
        )


__all__ = ["SqlAlchemySubscriptionPreparationRepository"]
