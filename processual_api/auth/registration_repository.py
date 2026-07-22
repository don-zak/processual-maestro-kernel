from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
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
        self._pending_users: dict[uuid.UUID, IdentityUser] = {}
        self._pending_action_tokens: dict[uuid.UUID, AuthActionToken] = {}

    async def email_exists(self, email_normalized: str) -> bool:
        statement = select(IdentityUser.id).where(IdentityUser.email_normalized == email_normalized)
        return (await self._session.scalar(statement)) is not None

    async def verification_principals_for_update(
        self,
        token_hash: str,
    ) -> tuple[AuthActionToken, IdentityUser] | None:
        statement = (
            select(AuthActionToken, IdentityUser)
            .join(IdentityUser, IdentityUser.id == AuthActionToken.user_id)
            .where(
                AuthActionToken.token_hash == token_hash,
                AuthActionToken.purpose == "verify_email",
            )
            .with_for_update()
        )
        row = (await self._session.execute(statement)).one_or_none()
        return None if row is None else (row[0], row[1])

    async def pending_user_for_update(self, email_normalized: str) -> IdentityUser | None:
        statement = (
            select(IdentityUser)
            .where(
                IdentityUser.email_normalized == email_normalized,
                IdentityUser.status == "pending_verification",
            )
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def latest_active_verification_token(
        self,
        user_id: uuid.UUID,
    ) -> AuthActionToken | None:
        statement = (
            select(AuthActionToken)
            .where(
                AuthActionToken.user_id == user_id,
                AuthActionToken.purpose == "verify_email",
                AuthActionToken.consumed_at.is_(None),
                AuthActionToken.invalidated_at.is_(None),
            )
            .order_by(AuthActionToken.created_at.desc())
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def invalidate_active_verification_tokens(
        self,
        user_id: uuid.UUID,
        *,
        invalidated_at: datetime,
    ) -> None:
        statement = (
            update(AuthActionToken)
            .where(
                AuthActionToken.user_id == user_id,
                AuthActionToken.purpose == "verify_email",
                AuthActionToken.consumed_at.is_(None),
                AuthActionToken.invalidated_at.is_(None),
            )
            .values(invalidated_at=invalidated_at)
        )
        await self._session.execute(statement)

    def add_verification_delivery(
        self,
        *,
        user: IdentityUser,
        action_token_id: uuid.UUID,
        action_token_hash: str,
        action_token_expires_at: datetime,
        outbox_id: uuid.UUID,
        payload_ciphertext: bytes,
        payload_key_version: str,
        available_at: datetime,
    ) -> None:
        action_token = AuthActionToken(
            id=action_token_id,
            user_id=user.id,
            purpose="verify_email",
            token_hash=action_token_hash,
            expires_at=action_token_expires_at,
            user=user,
        )
        self._session.add(action_token)
        self._session.add(
            AuthDeliveryOutbox(
                id=outbox_id,
                user_id=user.id,
                action_token_id=action_token_id,
                event_type="verify_email",
                payload_ciphertext=payload_ciphertext,
                payload_key_version=payload_key_version,
                available_at=available_at,
                attempt_count=0,
                user=user,
                action_token=action_token,
            )
        )

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
        self._pending_users[user_id] = user
        self._session.add(user)
        self._session.add(
            IdentityTermsAcceptance(
                id=uuid.uuid4(),
                user_id=user_id,
                terms_version=terms_version,
                accepted_at=accepted_at,
                user=user,
            )
        )
        action_token = AuthActionToken(
            id=action_token_id,
            user_id=user_id,
            purpose="verify_email",
            token_hash=action_token_hash,
            expires_at=action_token_expires_at,
            user=user,
        )
        self._pending_action_tokens[action_token_id] = action_token
        self._session.add(action_token)
        if organization_id is not None:
            if not organization_slug or not organization_name:
                raise ValueError("Organization registration requires slug and name.")
            organization = IdentityOrganization(
                id=organization_id,
                slug_normalized=organization_slug,
                display_name=organization_name,
                status="pending_review",
            )
            self._session.add(organization)
            self._session.add(
                OrganizationMembership(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    organization_id=organization_id,
                    role="organization_owner",
                    status="active",
                    joined_at=accepted_at,
                    user=user,
                    organization=organization,
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
        user = self._pending_users.get(user_id)
        action_token = self._pending_action_tokens.get(action_token_id)
        if user is None or action_token is None:
            raise ValueError("Delivery outbox requires pending registration principals.")
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
                user=user,
                action_token=action_token,
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
