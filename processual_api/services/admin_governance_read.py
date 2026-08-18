from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.models import AdministratorGovernanceAuditEvent
from processual_api.auth.models import AuthSession, IdentityPlatformAuthority, IdentityUser


@dataclass(frozen=True, slots=True)
class AdministratorAuthorityView:
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: str
    authority: str
    authority_status: str
    granted_at: datetime


@dataclass(frozen=True, slots=True)
class AdministratorActivityView:
    event_id: uuid.UUID
    event_type: str
    actor_user_id: uuid.UUID | None
    subject_user_id: uuid.UUID
    invitation_id: uuid.UUID | None
    permission: str | None
    reason: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AdministratorSessionView:
    session_id: uuid.UUID
    user_id: uuid.UUID
    authenticated_at: datetime
    mfa_satisfied_at: datetime | None
    last_seen_at: datetime | None
    expires_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None


class AdministratorGovernanceReadService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def list_administrators(self) -> tuple[AdministratorAuthorityView, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(IdentityUser, IdentityPlatformAuthority)
                    .join(
                        IdentityPlatformAuthority,
                        IdentityPlatformAuthority.user_id == IdentityUser.id,
                    )
                    .where(
                        IdentityPlatformAuthority.status == "active",
                        IdentityPlatformAuthority.authority.in_(
                            ("platform_admin", "platform_supervisor")
                        ),
                        IdentityUser.status != "deleted",
                    )
                    .order_by(
                        IdentityPlatformAuthority.authority,
                        IdentityUser.email_normalized,
                        IdentityPlatformAuthority.granted_at,
                    )
                )
            ).all()

        return tuple(
            AdministratorAuthorityView(
                user_id=user.id,
                email=user.email_normalized,
                display_name=user.display_name,
                user_status=user.status,
                authority=authority.authority,
                authority_status=authority.status,
                granted_at=authority.granted_at,
            )
            for user, authority in rows
        )

    async def list_activity(
        self,
        *,
        limit: int = 50,
    ) -> tuple[AdministratorActivityView, ...]:
        bounded_limit = max(1, min(limit, 200))
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(AdministratorGovernanceAuditEvent)
                    .order_by(AdministratorGovernanceAuditEvent.occurred_at.desc())
                    .limit(bounded_limit)
                )
            ).all()

        return tuple(
            AdministratorActivityView(
                event_id=row.id,
                event_type=row.event_type,
                actor_user_id=row.actor_user_id,
                subject_user_id=row.subject_user_id,
                invitation_id=row.invitation_id,
                permission=row.permission,
                reason=row.reason,
                occurred_at=row.occurred_at,
            )
            for row in rows
        )

    async def list_sessions(
        self,
        *,
        user_id: uuid.UUID,
    ) -> tuple[AdministratorSessionView, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(AuthSession)
                    .where(AuthSession.user_id == user_id)
                    .order_by(AuthSession.authenticated_at.desc())
                )
            ).all()

        return tuple(
            AdministratorSessionView(
                session_id=row.id,
                user_id=row.user_id,
                authenticated_at=row.authenticated_at,
                mfa_satisfied_at=row.mfa_satisfied_at,
                last_seen_at=row.last_seen_at,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
                revoke_reason=row.revoke_reason,
            )
            for row in rows
        )


__all__ = [
    "AdministratorActivityView",
    "AdministratorAuthorityView",
    "AdministratorGovernanceReadService",
    "AdministratorSessionView",
]
