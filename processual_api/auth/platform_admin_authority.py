from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status

from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityError,
    AdminMarketplaceIdentityAuthorityResolver,
)


def _authority_headers(current_user: dict[str, Any], request: Request | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if request is not None:
        session = str(request.headers.get("x-pmk-platform-admin-session") or "").strip()
        if session:
            headers["x-pmk-platform-admin-session"] = session
    email = str(current_user.get("email") or "").strip()
    if email:
        headers["x-pmk-admin-email"] = email
    return headers


async def require_active_platform_admin(
    current_user: dict[str, Any],
    request: Request | None = None,
) -> dict[str, Any]:
    """Resolve persisted super-admin authority instead of trusting role claims."""

    resolver = AdminMarketplaceIdentityAuthorityResolver()
    try:
        authority = await resolver.resolve_with_session(
            headers=_authority_headers(current_user, request),
            identity=current_user,
        )
    except AdminMarketplaceIdentityAuthorityError as exc:
        code = str(getattr(exc, "code", "") or "")
        http_status = (
            status.HTTP_401_UNAUTHORIZED
            if code in {"admin_identity_missing", "admin_session_missing", "admin_session_expired"}
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=http_status, detail=str(exc)) from exc

    role = str(getattr(authority, "role", "") or "").strip().lower()
    if role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External Evaluation Access administration is restricted to the persisted platform super administrator.",
        )
    return current_user


__all__ = ["require_active_platform_admin"]
