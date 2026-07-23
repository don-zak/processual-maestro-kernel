from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    AuthActionToken,
    AuthDeliveryOutbox,
    IdentityPlatformAuthority,
    IdentityUser,
    IdentityUserEmailAddress,
)


class SqlAlchemyRecoveryEmailVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def platform_admin_user(
        self,
        *,
        user_id: uuid.UUID,
    ) -> IdentityUser | None:
        return await self._session.scalar(
            select(IdentityUser)
            .join(
                IdentityPlatformAuthority,
                IdentityPlatformAuthority.user_id
                == IdentityUser.id,
            )
            .where(
                IdentityUser.id == user_id,
                IdentityUser.status == "active",
                IdentityUser.email_verified_at.is_not(None),
                IdentityPlatformAuthority.authority
                == "platform_admin",
                IdentityPlatformAuthority.status == "active",
            )
            .with_for_update()
        )

    async def pending_recovery_email_for_update(
        self,
        *,
        user_id: uuid.UUID,
    ) -> IdentityUserEmailAddress | None:
        return await self._session.scalar(
            select(IdentityUserEmailAddress)
            .where(
                IdentityUserEmailAddress.user_id == user_id,
                IdentityUserEmailAddress.purpose == "recovery",
                IdentityUserEmailAddress.status == "pending",
            )
            .with_for_update()
        )

    async def verification_principals_for_update(
        self,
        *,
        token_hash: str,
    ) -> tuple[
        AuthActionToken,
        IdentityUserEmailAddress,
    ] | None:
        result = await self._session.execute(
            select(
                AuthActionToken,
                IdentityUserEmailAddress,
            )
            .join(
                IdentityUserEmailAddress,
                IdentityUserEmailAddress.user_id
                == AuthActionToken.user_id,
            )
            .where(
                AuthActionToken.token_hash == token_hash,
                AuthActionToken.purpose
                == "verify_recovery_email",
                IdentityUserEmailAddress.purpose == "recovery",
            )
            .with_for_update()
        )
        return result.one_or_none()

    async def invalidate_active_tokens(
        self,
        *,
        user_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int:
        rows = list(
            (
                await self._session.scalars(
                    select(AuthActionToken)
                    .where(
                        AuthActionToken.user_id == user_id,
                        AuthActionToken.purpose
                        == "verify_recovery_email",
                        AuthActionToken.consumed_at.is_(None),
                    )
                    .with_for_update()
                )
            ).all()
        )

        for row in rows:
            row.consumed_at = invalidated_at

        return len(rows)

    def add_verification(
        self,
        *,
        token_id: uuid.UUID,
        outbox_id: uuid.UUID,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        payload_ciphertext: str,
        payload_key_version: str,
        available_at: datetime,
    ) -> tuple[AuthActionToken, AuthDeliveryOutbox]:
        token = AuthActionToken(
            id=token_id,
            user_id=user_id,
            purpose="verify_recovery_email",
            token_hash=token_hash,
            expires_at=expires_at,
            consumed_at=None,
            created_at=available_at,
        )

        outbox = AuthDeliveryOutbox(
            id=outbox_id,
            user_id=user_id,
            action_token_id=token_id,
            event_type="verify_recovery_email",
            payload_ciphertext=payload_ciphertext,
            payload_key_version=payload_key_version,
            available_at=available_at,
            attempt_count=0,
        )

        self._session.add(token)
        self._session.add(outbox)

        return token, outbox


class SqlAlchemyRecoveryEmailVerificationUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: (
            SqlAlchemyRecoveryEmailVerificationRepository
        )

    async def __aenter__(
        self,
    ) -> SqlAlchemyRecoveryEmailVerificationUnitOfWork:
        self._session = self._session_factory()
        self.repository = (
            SqlAlchemyRecoveryEmailVerificationRepository(
                self._session
            )
        )
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError(
                "Recovery-email verification unit of work "
                "is not active."
            )
        await self._session.commit()


__all__ = [
    "SqlAlchemyRecoveryEmailVerificationRepository",
    "SqlAlchemyRecoveryEmailVerificationUnitOfWork",
]
