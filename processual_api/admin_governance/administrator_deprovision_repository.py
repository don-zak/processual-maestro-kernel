from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.models import (
    AdministratorGovernanceAuditEvent,
    AdministratorPermissionGrant,
)
from processual_api.auth.models import (
    AuthRefreshToken,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
)


class SqlAlchemyAdministratorDeprovisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_platform_admin_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .join(IdentityUser, IdentityUser.id == IdentityPlatformAuthority.user_id)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_admin",
                IdentityPlatformAuthority.status == "active",
                IdentityUser.status == "active",
            )
            .with_for_update()
        )

    async def platform_supervisor_for_update(self, *, user_id: uuid.UUID):
        return await self._session.scalar(
            select(IdentityPlatformAuthority)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_supervisor",
            )
            .with_for_update()
        )

    async def active_permission_grants_for_update(self, *, user_id: uuid.UUID):
        result = await self._session.scalars(
            select(AdministratorPermissionGrant)
            .where(
                AdministratorPermissionGrant.user_id == user_id,
                AdministratorPermissionGrant.status == "active",
            )
            .order_by(AdministratorPermissionGrant.permission.asc())
            .with_for_update()
        )
        return tuple(result.all())

    async def revoke_all_sessions(
        self,
        *,
        user_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        session_ids = select(AuthSession.id).where(AuthSession.user_id == user_id)
        await self._session.execute(
            update(AuthRefreshToken)
            .where(
                AuthRefreshToken.session_id.in_(session_ids),
                AuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at, revoke_reason=reason)
        )

    def add_governance_audit_event(self, **values) -> AdministratorGovernanceAuditEvent:
        row = AdministratorGovernanceAuditEvent(**values)
        self._session.add(row)
        return row


class SqlAlchemyAdministratorDeprovisionUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyAdministratorDeprovisionRepository | None = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.repository = SqlAlchemyAdministratorDeprovisionRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None:
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Administrator deprovision unit of work is not active.")
        await self._session.commit()


__all__ = [
    "SqlAlchemyAdministratorDeprovisionRepository",
    "SqlAlchemyAdministratorDeprovisionUnitOfWork",
]
