from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import (
    AuthActionToken,
    AuthDeliveryOutbox,
    IdentityOrganization,
    IdentityTermsAcceptance,
    IdentityUser,
    OrganizationMembership,
)


class RegistrationConflictError(RuntimeError):
    """A uniqueness race prevented the registration transaction."""


class SqlAlchemyRegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def email_exists(self, email_normalized: str) -> bool:
        statement = select(IdentityUser.id).where(IdentityUser.email_normalized == email_normalized)
        return (await self._session.scalar(statement)) is not None

    def add_registration(
        self,
        *,
        user_id: uuid.UUID,
        email_normalized: str,
        display_name: str,
        password_hash: str,
        terms_version: str,
        accepted_at: datetime,
        action_token_id: uuid.UUID,
        action_token_hash: str,
        action_token_expires_at: datetime,
        organization_id: uuid.UUID | None = None,
        organization_slug: str | None = None,
        organization_name: str | None = None,
    ) -> None:
        user = IdentityUser(
            id=user_id,
            email_normalized=email_normalized,
            display_name=display_name,
            password_hash=password_hash,
            status="pending_verification",
        )
        self._session.add(user)
        self._session.add(
            IdentityTermsAcceptance(
                id=uuid.uuid4(),
                user_id=user_id,
                terms_version=terms_version,
                accepted_at=accepted_at,
            )
        )
        self._session.add(
            AuthActionToken(
                id=action_token_id,
                user_id=user_id,
                purpose="verify_email",
                token_hash=action_token_hash,
                expires_at=action_token_expires_at,
            )
        )
        if organization_id is not None:
            if not organization_slug or not organization_name:
                raise ValueError("Organization registration requires slug and name.")
            self._session.add(
                IdentityOrganization(
                    id=organization_id,
                    slug_normalized=organization_slug,
                    display_name=organization_name,
                    status="pending_review",
                )
            )
            self._session.add(
                OrganizationMembership(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    organization_id=organization_id,
                    role="organization_owner",
                    status="active",
                    joined_at=accepted_at,
                )
            )

    def add_delivery_outbox(
        self,
        *,
        outbox_id: uuid.UUID,
        user_id: uuid.UUID,
        action_token_id: uuid.UUID,
        event_type: str,
        payload_ciphertext: bytes,
        payload_key_version: str,
        available_at: datetime,
    ) -> None:
        self._session.add(
            AuthDeliveryOutbox(
                id=outbox_id,
                user_id=user_id,
                action_token_id=action_token_id,
                event_type=event_type,
                payload_ciphertext=payload_ciphertext,
                payload_key_version=payload_key_version,
                available_at=available_at,
                attempt_count=0,
            )
        )


class SqlAlchemyRegistrationUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.repository: SqlAlchemyRegistrationRepository | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyRegistrationUnitOfWork:
        self._session = self._session_factory()
        self.repository = SqlAlchemyRegistrationRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Registration unit of work is not active.")
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise RegistrationConflictError("Registration conflict.") from exc
        self._committed = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._session is None:
            return
        if exc is not None or not self._committed:
            await self._session.rollback()
        await self._session.close()


__all__ = [
    "RegistrationConflictError",
    "SqlAlchemyRegistrationRepository",
    "SqlAlchemyRegistrationUnitOfWork",
]
