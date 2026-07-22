from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    AuthMfaFactor,
    AuthMfaRecoveryCode,
    AuthSession,
    IdentityUser,
    OrganizationMembership,
)


class SqlAlchemyMfaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def user_email(self, user_id: uuid.UUID) -> str | None:
        return await self._session.scalar(
            select(IdentityUser.email_normalized)
            .where(IdentityUser.id == user_id)
            .with_for_update()
        )

    async def is_required_by_role(self, user_id: uuid.UUID) -> bool:
        membership_id = await self._session.scalar(
            select(OrganizationMembership.id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == "active",
                OrganizationMembership.role.in_(("organization_owner", "organization_admin")),
            )
            .limit(1)
        )
        return membership_id is not None

    async def active_factor_for_update(self, user_id: uuid.UUID) -> AuthMfaFactor | None:
        return await self._session.scalar(
            select(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "active")
            .order_by(AuthMfaFactor.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def pending_factor_for_update(self, user_id: uuid.UUID) -> AuthMfaFactor | None:
        return await self._session.scalar(
            select(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "pending")
            .order_by(AuthMfaFactor.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def factor_statuses(self, user_id: uuid.UUID) -> tuple[bool, bool]:
        rows = set(
            (
                await self._session.scalars(
                    select(AuthMfaFactor.status).where(AuthMfaFactor.user_id == user_id)
                )
            ).all()
        )
        return "active" in rows, "pending" in rows

    async def disable_pending_factors(self, user_id: uuid.UUID, *, disabled_at: datetime) -> None:
        await self._session.execute(
            update(AuthMfaFactor)
            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "pending")
            .values(status="disabled", disabled_at=disabled_at)
        )

    def add_pending_factor(
        self,
        *,
        factor_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str,
        ciphertext: bytes,
        key_version: str,
    ) -> None:
        self._session.add(
            AuthMfaFactor(
                id=factor_id,
                user_id=user_id,
                factor_type="totp",
                label=label,
                status="pending",
                secret_ciphertext=ciphertext,
                secret_key_version=key_version,
            )
        )

    async def replace_recovery_codes(
        self,
        factor_id: uuid.UUID,
        *,
        code_hashes: tuple[str, ...],
    ) -> None:
        await self._session.execute(
            delete(AuthMfaRecoveryCode).where(AuthMfaRecoveryCode.factor_id == factor_id)
        )
        self._session.add_all(
            AuthMfaRecoveryCode(factor_id=factor_id, code_hash=code_hash)
            for code_hash in code_hashes
        )

    async def unused_recovery_code_for_update(
        self,
        factor_id: uuid.UUID,
        code_hash: str,
    ) -> AuthMfaRecoveryCode | None:
        return await self._session.scalar(
            select(AuthMfaRecoveryCode)
            .where(
                AuthMfaRecoveryCode.factor_id == factor_id,
                AuthMfaRecoveryCode.code_hash == code_hash,
                AuthMfaRecoveryCode.used_at.is_(None),
            )
            .with_for_update()
        )

    async def recovery_codes_remaining(self, factor_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(AuthMfaRecoveryCode)
            .where(
                AuthMfaRecoveryCode.factor_id == factor_id,
                AuthMfaRecoveryCode.used_at.is_(None),
            )
        )
        return int(count or 0)

    async def session_for_update(
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

    async def revoke_other_sessions(
        self,
        *,
        user_id: uuid.UUID,
        current_session_id: uuid.UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.id != current_session_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at, revoke_reason=reason)
        )


class SqlAlchemyMfaUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyMfaRepository | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyMfaUnitOfWork:
        self._session = self._session_factory()
        self.repository = SqlAlchemyMfaRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("MFA unit of work is not active.")
        await self._session.commit()
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = ["SqlAlchemyMfaRepository", "SqlAlchemyMfaUnitOfWork"]
