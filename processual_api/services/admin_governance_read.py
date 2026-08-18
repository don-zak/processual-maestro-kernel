from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.auth.models import IdentityPlatformAuthority, IdentityUser


@dataclass(frozen=True, slots=True)
class AdministratorAuthorityView:
    user_id: uuid.UUID
    email: str
    display_name: str
    user_status: str
    authority: str
    authority_status: str
    granted_at: datetime


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


__all__ = [
    "AdministratorAuthorityView",
    "AdministratorGovernanceReadService",
]
