from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select

from processual_api.auth.models import OrganizationMembership
from processual_api.db.session import get_session_factory


class OrganizationAuthorityError(PermissionError):
    """Raised when organization authority cannot be established server-side."""


@dataclass(frozen=True, slots=True)
class OrganizationAuthority:
    user_id: str
    organization_id: str
    role: str


async def resolve_active_organization_authority(
    *,
    user_id: str,
    organization_id: str,
) -> OrganizationAuthority:
    """Resolve active organization membership from the authoritative database.

    Caller-provided JWT/body roles are intentionally ignored. Missing, invalid,
    inactive, suspended, or revoked memberships fail closed.
    """

    try:
        user_uuid = uuid.UUID(str(user_id))
        organization_uuid = uuid.UUID(str(organization_id))
    except (TypeError, ValueError) as exc:
        raise OrganizationAuthorityError("invalid organization authority identity") from exc

    try:
        session_factory = get_session_factory()
        async with session_factory() as db_session:
            membership = (
                await db_session.execute(
                    select(OrganizationMembership).where(
                        OrganizationMembership.user_id == user_uuid,
                        OrganizationMembership.organization_id == organization_uuid,
                        OrganizationMembership.status == "active",
                    )
                )
            ).scalar_one_or_none()
    except OrganizationAuthorityError:
        raise
    except Exception as exc:
        raise OrganizationAuthorityError("organization authority unavailable") from exc

    if membership is None:
        raise OrganizationAuthorityError("active organization membership required")

    role = str(membership.role or "").strip()
    if role not in {
        "organization_owner",
        "organization_admin",
        "operator",
        "auditor",
        "viewer",
    }:
        raise OrganizationAuthorityError("organization role is not recognized")

    return OrganizationAuthority(
        user_id=str(user_uuid),
        organization_id=str(organization_uuid),
        role=role,
    )


def require_organization_role(
    authority: OrganizationAuthority,
    *allowed_roles: str,
) -> OrganizationAuthority:
    allowed = {str(role).strip() for role in allowed_roles if str(role).strip()}
    if not allowed or authority.role not in allowed:
        raise OrganizationAuthorityError("organization role does not permit this operation")
    return authority


__all__ = [
    "OrganizationAuthority",
    "OrganizationAuthorityError",
    "require_organization_role",
    "resolve_active_organization_authority",
]
