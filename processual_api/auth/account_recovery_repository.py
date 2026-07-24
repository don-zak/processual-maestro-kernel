from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    AuthAccountRecoveryRequest,
    AuthDeliveryOutbox,
    IdentityUser,
    IdentityUserEmailAddress,
)


class SqlAlchemyAccountRecoveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def eligible_principal_by_login(
        self,
        *,
        login_normalized: str,
    ) -> (
        tuple[
            IdentityUser,
            IdentityUserEmailAddress,
        ]
        | None
    ):
        result = await self._session.execute(
            select(
                IdentityUser,
                IdentityUserEmailAddress,
            )
            .join(
                IdentityUserEmailAddress,
                IdentityUserEmailAddress.user_id == IdentityUser.id,
            )
            .where(
                or_(
                    IdentityUser.email_normalized == login_normalized,
                    IdentityUserEmailAddress.email_normalized == login_normalized,
                ),
                IdentityUser.status == "active",
                IdentityUserEmailAddress.purpose == "recovery",
                IdentityUserEmailAddress.status == "verified",
                IdentityUserEmailAddress.verified_at.is_not(None),
                IdentityUserEmailAddress.revoked_at.is_(None),
            )
            .with_for_update()
        )

        row = result.one_or_none()

        if row is None:
            return None

        return row[0], row[1]

    async def invalidate_active_requests(
        self,
        *,
        user_id: uuid.UUID,
        invalidated_at: datetime,
    ) -> int:
        requests = list(
            (
                await self._session.scalars(
                    select(AuthAccountRecoveryRequest)
                    .where(
                        AuthAccountRecoveryRequest.user_id == user_id,
                        AuthAccountRecoveryRequest.state.in_(
                            (
                                "pending",
                                "verified",
                            )
                        ),
                        AuthAccountRecoveryRequest.revoked_at.is_(None),
                    )
                    .with_for_update()
                )
            ).all()
        )

        for request in requests:
            request.state = "revoked"
            request.revoked_at = invalidated_at
            request.updated_at = invalidated_at

        return len(requests)

    def add_request_with_delivery(
        self,
        *,
        request_id: uuid.UUID,
        outbox_id: uuid.UUID,
        user_id: uuid.UUID,
        recovery_email_id: uuid.UUID,
        purpose: str,
        state: str,
        verification_token_hash: str,
        completion_token_hash: str | None,
        attempt_count: int,
        expires_at: datetime,
        verified_at: datetime | None,
        completed_at: datetime | None,
        revoked_at: datetime | None,
        created_at: datetime,
        updated_at: datetime,
        payload_ciphertext: bytes,
        payload_key_version: str,
        available_at: datetime,
    ) -> tuple[
        AuthAccountRecoveryRequest,
        AuthDeliveryOutbox,
    ]:
        request = AuthAccountRecoveryRequest(
            id=request_id,
            user_id=user_id,
            recovery_email_id=recovery_email_id,
            purpose=purpose,
            state=state,
            verification_token_hash=(verification_token_hash),
            completion_token_hash=completion_token_hash,
            attempt_count=attempt_count,
            expires_at=expires_at,
            verified_at=verified_at,
            completed_at=completed_at,
            revoked_at=revoked_at,
            created_at=created_at,
            updated_at=updated_at,
        )

        outbox = AuthDeliveryOutbox(
            id=outbox_id,
            user_id=user_id,
            action_token_id=None,
            account_recovery_request_id=request_id,
            event_type="account_recovery_verification",
            payload_ciphertext=payload_ciphertext,
            payload_key_version=payload_key_version,
            available_at=available_at,
            attempt_count=0,
            account_recovery_request=request,
        )

        self._session.add(request)
        self._session.add(outbox)

        return request, outbox

    async def request_for_update(
        self,
        *,
        request_id: uuid.UUID,
    ) -> AuthAccountRecoveryRequest | None:
        return await self._session.scalar(
            select(AuthAccountRecoveryRequest).where(AuthAccountRecoveryRequest.id == request_id).with_for_update()
        )


class SqlAlchemyAccountRecoveryUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyAccountRecoveryRepository
        self._committed = False

    async def __aenter__(
        self,
    ) -> SqlAlchemyAccountRecoveryUnitOfWork:
        self._session = self._session_factory()
        self.repository = SqlAlchemyAccountRecoveryRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Account recovery unit of work is not active.")

        await self._session.commit()
        self._committed = True

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        if self._session is None:
            return

        try:
            if exc is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()


__all__ = [
    "SqlAlchemyAccountRecoveryRepository",
    "SqlAlchemyAccountRecoveryUnitOfWork",
]
