from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.models import AdministratorInvitation
from processual_api.auth.models import IdentityPlatformAuthority, IdentityUser


class SqlAlchemyAdministratorInvitationRepository:
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

    async def identity_exists(self, *, email_normalized: str) -> bool:
        user_id = await self._session.scalar(
            select(IdentityUser.id)
            .where(IdentityUser.email_normalized == email_normalized)
            .limit(1)
        )
        return user_id is not None

    async def active_invitation_for_email(self, *, email_normalized: str):
        now = datetime.now(UTC)
        return await self._session.scalar(
            select(AdministratorInvitation)
            .where(
                AdministratorInvitation.email_normalized == email_normalized,
                AdministratorInvitation.status == "pending",
                AdministratorInvitation.expires_at > now,
            )
            .order_by(AdministratorInvitation.created_at.desc())
            .limit(1)
        )

    def add_invitation(self, **values) -> AdministratorInvitation:
        row = AdministratorInvitation(
            id=values["invitation_id"],
            email_normalized=values["email_normalized"],
            supervision_level=values["supervision_level"],
            token_hash=values["token_hash"],
            status=values["status"],
            invited_by_user_id=values["invited_by_user_id"],
            invite_reason=values["invite_reason"],
            expires_at=values["expires_at"],
            created_at=values["created_at"],
            updated_at=values["created_at"],
        )
        self._session.add(row)
        return row


class SqlAlchemyAdministratorInvitationUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyAdministratorInvitationRepository | None = None
        self._committed = False

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyAdministratorInvitationRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Administrator invitation unit of work is not active.")
        await self._session.commit()
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = [
    "SqlAlchemyAdministratorInvitationRepository",
    "SqlAlchemyAdministratorInvitationUnitOfWork",
]
