from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status

from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.runtime import (
    AdminMarketplaceRuntimeUnavailableError,
    build_admin_marketplace_runtime,
)


def _identity_principal(current_user: dict[str, Any]) -> tuple[str, str]:
    if current_user.get("session_type") != "identity_user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity session required.",
        )

    user_id = str(current_user.get("user_id") or "").strip()
    session_id = str(current_user.get("session_id") or "").strip()
    if not user_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity session.",
        )
    return user_id, session_id


async def require_active_platform_admin(
    current_user: dict[str, Any],
    request: Request | None = None,
) -> dict[str, Any]:
    """Resolve persisted platform-admin authority through the canonical runtime.

    Evaluation administration is intentionally unavailable to API-key identities
    and role/scope claims. POST and DELETE operations additionally require the
    recent MFA step-up already computed by the authoritative identity resolver.
    """

    user_id, session_id = _identity_principal(current_user)
    try:
        runtime = await build_admin_marketplace_runtime()
        authority = await runtime.authority_resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active platform administrator authority is required.",
        ) from exc
    except AdminMarketplaceRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform administrator authority is temporarily unavailable.",
        ) from exc

    if not authority.active_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active platform administrator authority is required.",
        )

    sensitive_request = request is not None and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    if sensitive_request and not authority.recent_mfa_step_up:
        raise HTTPException(
            status_code=428,
            detail="Recent MFA step-up is required.",
        )
    return current_user


__all__ = ["require_active_platform_admin"]
