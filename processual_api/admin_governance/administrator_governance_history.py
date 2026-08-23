from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_governance.models import AdministratorPermissionGrant
from processual_api.auth.models import IdentityPlatformAuthority, IdentityUser


@dataclass(frozen=True, slots=True)
class AdministratorAuthorityHistoryView:
    authority: str
    status: str
    granted_by_user_id: uuid.UUID | None
    grant_reason: str
    granted_at: datetime
    revoked_by_user_id: uuid.UUID | None
    revoke_reason: str | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdministratorPermissionHistoryView:
    permission: str
    status: str
    source_invitation_id: uuid.UUID
    granted_by_user_id: uuid.UUID | None
    grant_reason: str
    granted_at: datetime
    revoked_by_user_id: uuid.UUID | None
    revocation_reason: str | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdministratorGovernanceHistoryView:
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: str
    authorities: tuple[AdministratorAuthorityHistoryView, ...]
    permissions: tuple[AdministratorPermissionHistoryView, ...]


class AdministratorGovernanceHistoryService:
    def __init__(self, *, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_history(
        self,
        *,
        user_id: uuid.UUID,
    ) -> AdministratorGovernanceHistoryView | None:
        async with self._session_factory() as session:
            user = await session.scalar(
                select(IdentityUser).where(IdentityUser.id == user_id)
            )
            if user is None:
                return None

            authority_rows = tuple(
                (
                    await session.scalars(
                        select(IdentityPlatformAuthority)
                        .where(IdentityPlatformAuthority.user_id == user_id)
                        .order_by(
                            IdentityPlatformAuthority.granted_at.asc(),
                            IdentityPlatformAuthority.authority.asc(),
                        )
                    )
                ).all()
            )
            permission_rows = tuple(
                (
                    await session.scalars(
                        select(AdministratorPermissionGrant)
                        .where(AdministratorPermissionGrant.user_id == user_id)
                        .order_by(
                            AdministratorPermissionGrant.granted_at.asc(),
                            AdministratorPermissionGrant.permission.asc(),
                        )
                    )
                ).all()
            )

        return AdministratorGovernanceHistoryView(
            user_id=user.id,
            email=user.email_normalized,
            display_name=user.display_name,
            user_status=user.status,
            authorities=tuple(
                AdministratorAuthorityHistoryView(
                    authority=row.authority,
                    status=row.status,
                    granted_by_user_id=row.granted_by_user_id,
                    grant_reason=row.grant_reason,
                    granted_at=row.granted_at,
                    revoked_by_user_id=row.revoked_by_user_id,
                    revoke_reason=row.revoke_reason,
                    revoked_at=row.revoked_at,
                )
                for row in authority_rows
            ),
            permissions=tuple(
                AdministratorPermissionHistoryView(
                    permission=row.permission,
                    status=row.status,
                    source_invitation_id=row.source_invitation_id,
                    granted_by_user_id=row.granted_by_user_id,
                    grant_reason=row.grant_reason,
                    granted_at=row.granted_at,
                    revoked_by_user_id=row.revoked_by_user_id,
                    revocation_reason=row.revocation_reason,
                    revoked_at=row.revoked_at,
                )
                for row in permission_rows
            ),
        )


__all__ = [
    "AdministratorAuthorityHistoryView",
    "AdministratorGovernanceHistoryService",
    "AdministratorGovernanceHistoryView",
    "AdministratorPermissionHistoryView",
]
