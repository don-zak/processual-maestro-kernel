from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    IdentityPlatformAuthority,
    IdentityUser,
    IdentityUserEmailAddress,
)


class AdminRecoveryEmailConflictError(RuntimeError):
    pass


class SqlAlchemyAdminRecoveryEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def platform_admin_user(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityUser)
            .join(
                IdentityPlatformAuthority,
                IdentityPlatformAuthority.user_id == IdentityUser.id,
            )
            .where(
                IdentityUser.id == user_id,
                IdentityUser.status == "active",
                IdentityPlatformAuthority.authority == "platform_admin",
                IdentityPlatformAuthority.status == "active",
            )
        )

    async def email_owner(self, *, email_normalized: str):
        primary = await self._session.scalar(
            select(IdentityUser.id).where(
                IdentityUser.email_normalized == email_normalized
            )
        )
        if primary is not None:
            return primary
        return await self._session.scalar(
            select(IdentityUserEmailAddress.user_id).where(
                IdentityUserEmailAddress.email_normalized == email_normalized,
                IdentityUserEmailAddress.status != "revoked",
            )
        )

    async def recovery_email_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityUserEmailAddress)
            .where(
                IdentityUserEmailAddress.user_id == user_id,
                IdentityUserEmailAddress.purpose == "recovery",
            )
            .with_for_update()
        )

    def add_recovery_email(
        self,
        *,
        user_id: uuid.UUID,
        email_normalized: str,
        now: datetime,
    ):
        row = IdentityUserEmailAddress(
            user_id=user_id,
            email_normalized=email_normalized,
            purpose="recovery",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        return row


class SqlAlchemyAdminRecoveryEmailUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session = None
        self.repository = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyAdminRecoveryEmailRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Recovery-email unit of work is not active.")
        try:
            await self._session.commit()
        except Exception as exc:
            await self._session.rollback()
            raise AdminRecoveryEmailConflictError(
                "Recovery email conflicts with an existing identity."
            ) from exc
