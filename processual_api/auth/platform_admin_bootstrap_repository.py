from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    IdentityPlatformAuthority,
    IdentityUser,
)

PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID = 781_204_601


class PlatformAdminBootstrapConflictError(RuntimeError):
    """A uniqueness or concurrency conflict prevented bootstrap."""


class SqlAlchemyPlatformAdminBootstrapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def acquire_bootstrap_lock(self) -> None:
        await self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID
                )
            )
        )

    async def platform_admin_authority_exists(self) -> bool:
        authority_id = await self._session.scalar(
            select(IdentityPlatformAuthority.id)
            .where(
                IdentityPlatformAuthority.authority
                == "platform_admin",
                IdentityPlatformAuthority.status.in_(
                    ("active", "revoked")
                ),
            )
            .limit(1)
        )
        return authority_id is not None

    async def email_exists(
        self,
        email_normalized: str,
    ) -> bool:
        user_id = await self._session.scalar(
            select(IdentityUser.id)
            .where(
                IdentityUser.email_normalized
                == email_normalized
            )
            .limit(1)
        )
        return user_id is not None

    def add_first_platform_admin(
        self,
        *,
        user_id: uuid.UUID,
        authority_id: uuid.UUID,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        created_at: datetime,
    ) -> None:
        user = IdentityUser(
            id=user_id,
            email_normalized=email_normalized,
            display_name=display_name,
            password_hash=password_hash,
            status="active",
            email_verified_at=created_at,
            password_changed_at=created_at,
            failed_login_count=0,
            locked_until=None,
        )
        authority = IdentityPlatformAuthority(
            id=authority_id,
            user_id=user_id,
            authority="platform_admin",
            status="active",
            granted_by_user_id=None,
            grant_reason="initial_platform_admin_bootstrap",
            granted_at=created_at,
            revoked_by_user_id=None,
            revoke_reason=None,
            revoked_at=None,
            user=user,
        )
        self._session.add(user)
        self._session.add(authority)


class SqlAlchemyPlatformAdminBootstrapUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: (
            SqlAlchemyPlatformAdminBootstrapRepository | None
        ) = None
        self._committed = False

    async def __aenter__(
        self,
    ) -> SqlAlchemyPlatformAdminBootstrapUnitOfWork:
        self._session = self._session_factory()
        self.repository = (
            SqlAlchemyPlatformAdminBootstrapRepository(
                self._session
            )
        )
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError(
                "Platform-admin bootstrap unit of work "
                "is not active."
            )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise PlatformAdminBootstrapConflictError(
                "Platform-admin bootstrap conflict."
            ) from exc
        self._committed = True

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = [
    "PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID",
    "PlatformAdminBootstrapConflictError",
    "SqlAlchemyPlatformAdminBootstrapRepository",
    "SqlAlchemyPlatformAdminBootstrapUnitOfWork",
]
