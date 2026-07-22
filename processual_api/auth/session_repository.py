from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    AuthMfaFactor,
    AuthRefreshToken,
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
    OrganizationMembership,
)
from processual_api.auth.session_contracts import SessionView


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_for_login(self, email_normalized: str) -> IdentityUser | None:
        return await self._session.scalar(
            select(IdentityUser)
            .where(IdentityUser.email_normalized == email_normalized)
            .with_for_update()
        )

    async def active_organization_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return await self._session.scalar(
            select(OrganizationMembership.organization_id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == "active",
            )
            .order_by(OrganizationMembership.created_at)
            .limit(1)
        )

    async def active_platform_authorities(
        self,
        user_id: uuid.UUID,
    ) -> tuple[str, ...]:
        result = await self._session.scalars(
            select(IdentityPlatformAuthority.authority)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.status == "active",
            )
            .order_by(
                IdentityPlatformAuthority.authority,
                IdentityPlatformAuthority.created_at,
            )
        )
        return tuple(result.all())
    async def requires_mfa(self, user_id: uuid.UUID) -> bool:
        factor_id = await self._session.scalar(
            select(AuthMfaFactor.id)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "active")
            .limit(1)
        )
        privileged_membership_id = await self._session.scalar(
            select(OrganizationMembership.id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == "active",
                OrganizationMembership.role.in_(("organization_owner", "organization_admin")),
            )
            .limit(1)
        )
        active_platform_admin_authority_id = await self._session.scalar(
            select(IdentityPlatformAuthority.id)
            .where(
                IdentityPlatformAuthority.user_id == user_id,
                IdentityPlatformAuthority.authority == "platform_admin",
                IdentityPlatformAuthority.status == "active",
            )
            .limit(1)
        )
        return (
            factor_id is not None
            or privileged_membership_id is not None
            or active_platform_admin_authority_id is not None
        )

    def add_session(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        refresh_family_id: uuid.UUID,
        refresh_token_id: uuid.UUID,
        refresh_token_hash: str,
        authenticated_at: datetime,
        expires_at: datetime,
        mfa_satisfied_at: datetime | None = None,
    ) -> None:
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            refresh_family_id=refresh_family_id,
            authenticated_at=authenticated_at,
            last_seen_at=authenticated_at,
            expires_at=expires_at,
            mfa_satisfied_at=mfa_satisfied_at,
        )
        self._session.add(auth_session)
        self._session.add(
            AuthRefreshToken(
                id=refresh_token_id,
                session_id=session_id,
                token_hash=refresh_token_hash,
                issued_at=authenticated_at,
                expires_at=expires_at,
                session=auth_session,
            )
        )

    async def refresh_principals_for_update(
        self,
        token_hash: str,
    ) -> tuple[AuthRefreshToken, AuthSession, IdentityUser] | None:
        row = (
            await self._session.execute(
                select(AuthRefreshToken, AuthSession, IdentityUser)
                .join(AuthSession, AuthSession.id == AuthRefreshToken.session_id)
                .join(IdentityUser, IdentityUser.id == AuthSession.user_id)
                .where(AuthRefreshToken.token_hash == token_hash)
                .with_for_update(of=(AuthRefreshToken, AuthSession, IdentityUser))
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1], row[2])

    def rotate_refresh_token(
        self,
        *,
        previous: AuthRefreshToken,
        token_id: uuid.UUID,
        token_hash: str,
        rotated_at: datetime,
        expires_at: datetime,
    ) -> None:
        previous.consumed_at = rotated_at
        self._session.add(
            AuthRefreshToken(
                id=token_id,
                session_id=previous.session_id,
                parent_token_id=previous.id,
                token_hash=token_hash,
                issued_at=rotated_at,
                expires_at=expires_at,
            )
        )

    async def revoke_family(
        self,
        auth_session: AuthSession,
        *,
        revoked_at: datetime,
        reason: str,
        reuse_token: AuthRefreshToken | None = None,
    ) -> None:
        auth_session.revoked_at = revoked_at
        auth_session.revoke_reason = reason
        if reuse_token is not None:
            reuse_token.reuse_detected_at = revoked_at
        await self._session.execute(
            update(AuthRefreshToken)
            .where(
                AuthRefreshToken.session_id == auth_session.id,
                AuthRefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_all_for_user(
        self,
        user_id: uuid.UUID,
        *,
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

    async def sessions_for_user(self, user_id: uuid.UUID) -> tuple[SessionView, ...]:
        rows = (
            await self._session.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
                .order_by(AuthSession.authenticated_at.desc())
            )
        ).all()
        return tuple(
            SessionView(
                id=row.id,
                authenticated_at=row.authenticated_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
            )
            for row in rows
        )

    async def owned_session_for_update(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AuthSession | None:
        return await self._session.scalar(
            select(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
            .with_for_update()
        )


class SqlAlchemySessionUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemySessionRepository | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemySessionUnitOfWork:
        self._session = self._session_factory()
        self.repository = SqlAlchemySessionRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Session unit of work is not active.")
        await self._session.commit()
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = ["SqlAlchemySessionRepository", "SqlAlchemySessionUnitOfWork"]
