from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import IdentityPlatformAuthority, IdentityUser


class SqlAlchemyPlatformSupervisorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_platform_admin(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .join(IdentityUser, IdentityUser.id == IdentityPlatformAuthority.user_id)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_admin",
                IdentityPlatformAuthority.status == "active",
                IdentityUser.status == "active",
            )
        )

    async def active_user(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityUser).where(
                IdentityUser.id == user_id,
                IdentityUser.status == "active",
                IdentityUser.email_verified_at.is_not(None),
            )
        )

    async def authority_for_update(
        self,
        *,
        user_id: uuid.UUID,
        authority: str,
    ):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == authority,
            )
            .with_for_update()
        )

    def add_supervisor_authority(
        self,
        *,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        grant_reason: str,
        now: datetime,
    ):
        row = IdentityPlatformAuthority(
            user_id=user_id,
            authority="platform_supervisor",
            status="active",
            granted_by_user_id=granted_by_user_id,
            grant_reason=grant_reason,
            granted_at=now,
        )
        self._session.add(row)
        return row


class SqlAlchemyPlatformSupervisorUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session = None
        self.repository = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyPlatformSupervisorRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Supervisor unit of work is not active.")
        await self._session.commit()
