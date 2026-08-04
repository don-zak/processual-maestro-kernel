from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAuthorityContext,
    authority_context,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.auth.models import (
    AuthSession,
    IdentityPlatformAuthority,
    IdentityUser,
)

PLATFORM_ADMIN_AUTHORITY = "platform_admin"
ACTIVE_STATUS = "active"


class AdminMarketplaceIdentityAuthorityResolver:
    """Resolve trusted Admin Marketplace authority from persisted identity state."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
        clock: Callable[[], datetime] | None = None,
        mfa_step_up_max_age: timedelta = timedelta(minutes=5),
    ) -> None:
        if mfa_step_up_max_age < timedelta(minutes=1):
            raise ValueError("MFA step-up lifetime must be at least one minute.")

        if mfa_step_up_max_age > timedelta(minutes=30):
            raise ValueError("MFA step-up lifetime must not exceed thirty minutes.")

        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mfa_step_up_max_age = mfa_step_up_max_age

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Identity authority clock must be timezone-aware.")
        return now

    async def resolve(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> AdminMarketplaceAuthorityContext:
        try:
            parsed_user_id = uuid.UUID(user_id)
            parsed_session_id = uuid.UUID(session_id)
        except (TypeError, ValueError) as exc:
            raise AdminMarketplaceAuthorityDeniedError("Valid identity user and session are required.") from exc

        now = self._now()

        statement = (
            select(
                AuthSession,
                IdentityUser,
                IdentityPlatformAuthority,
            )
            .join(
                IdentityUser,
                IdentityUser.id == AuthSession.user_id,
            )
            .join(
                IdentityPlatformAuthority,
                IdentityPlatformAuthority.user_id == IdentityUser.id,
            )
            .where(
                AuthSession.id == parsed_session_id,
                AuthSession.user_id == parsed_user_id,
                IdentityUser.id == parsed_user_id,
                IdentityUser.status == ACTIVE_STATUS,
                IdentityPlatformAuthority.authority == PLATFORM_ADMIN_AUTHORITY,
                IdentityPlatformAuthority.status == ACTIVE_STATUS,
            )
        )

        async with self._session_factory() as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            raise AdminMarketplaceAuthorityDeniedError("Active platform administrator authority is required.")

        auth_session, _identity_user, _platform_authority = row

        if auth_session.revoked_at is not None or auth_session.expires_at <= now:
            raise AdminMarketplaceAuthorityDeniedError("Active identity session is required.")

        recent_mfa_step_up = (
            auth_session.mfa_satisfied_at is not None
            and auth_session.mfa_satisfied_at >= now - self._mfa_step_up_max_age
        )

        return authority_context(
            user_id=str(parsed_user_id),
            session_id=str(parsed_session_id),
            platform_authorities=(PLATFORM_ADMIN_AUTHORITY,),
            active_platform_admin=True,
            recent_mfa_step_up=recent_mfa_step_up,
        )


__all__ = [
    "AdminMarketplaceIdentityAuthorityResolver",
]
