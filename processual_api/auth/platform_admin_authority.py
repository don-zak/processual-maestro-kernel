from __future__ import annotations

from fastapi import HTTPException, status

from processual_api.admin_marketplace.errors import AdminMarketplaceAuthorityDeniedError
from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityResolver,
)
from processual_api.db.session import get_session_factory

SUPER_ADMIN_AUTHORITY = "platform_admin"


async def require_active_platform_admin(current_user: dict) -> None:
    """Require the platform's exclusive Super Administrator identity authority.

    Legacy admin roles, owner/security/billing roles, wildcard scopes, API keys,
    and non-identity sessions are intentionally insufficient.
    """

    if current_user.get("session_type") != "identity_user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exclusive super-administrator identity authority is required.",
        )

    user_id = str(current_user.get("user_id") or "").strip()
    session_id = str(current_user.get("session_id") or "").strip()
    if not user_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exclusive super-administrator identity authority is required.",
        )

    resolver = AdminMarketplaceIdentityAuthorityResolver(
        session_factory=get_session_factory(),
    )
    try:
        authority = await resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exclusive super-administrator identity authority is required.",
        ) from exc

    if (
        not authority.active_platform_admin
        or SUPER_ADMIN_AUTHORITY not in authority.platform_authorities
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exclusive super-administrator identity authority is required.",
        )


__all__ = ["SUPER_ADMIN_AUTHORITY", "require_active_platform_admin"]
