from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityService,
)
from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityResolver,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.db.session import get_session_factory
from processual_api.settings import settings


class AdminMarketplaceRuntimeUnavailableError(RuntimeError):
    """Admin Marketplace read authority is unavailable."""


@dataclass(frozen=True, slots=True)
class AdminMarketplaceRuntime:
    authority_resolver: AdminMarketplaceIdentityAuthorityResolver
    eligibility_service: AdminMarketplaceEligibilityService


async def build_admin_marketplace_runtime() -> AdminMarketplaceRuntime:
    try:
        session_factory = get_session_factory()
        mfa_step_up_max_age = timedelta(
            seconds=settings.auth_mfa_step_up_seconds,
        )

        def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
            return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

        authority_resolver = AdminMarketplaceIdentityAuthorityResolver(
            session_factory=session_factory,
            mfa_step_up_max_age=mfa_step_up_max_age,
        )
        eligibility_service = AdminMarketplaceEligibilityService(
            unit_of_work_factory=unit_of_work_factory,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise AdminMarketplaceRuntimeUnavailableError("Admin Marketplace read authority is unavailable.") from exc

    return AdminMarketplaceRuntime(
        authority_resolver=authority_resolver,
        eligibility_service=eligibility_service,
    )


__all__ = [
    "AdminMarketplaceRuntime",
    "AdminMarketplaceRuntimeUnavailableError",
    "build_admin_marketplace_runtime",
]
