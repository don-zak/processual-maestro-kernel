from __future__ import annotations

from processual_api.admin_marketplace.errors import (
    AdminMarketplaceError,
)


class AdminMarketplaceApplicationError(AdminMarketplaceError):
    """Base error for marketplace application workflows."""


class AdminMarketplaceResourceNotFoundError(AdminMarketplaceApplicationError):
    """A commercial resource does not exist."""


class AdminMarketplaceTransitionError(AdminMarketplaceApplicationError):
    """A requested commercial transition is not allowed."""


class AdminMarketplaceChannelPolicyError(AdminMarketplaceApplicationError):
    """A selected sales channel violates eligibility policy."""


class AdminMarketplaceActivationPolicyError(AdminMarketplaceApplicationError):
    """Entitlement activation violates explicit activation policy."""


__all__ = [
    "AdminMarketplaceActivationPolicyError",
    "AdminMarketplaceApplicationError",
    "AdminMarketplaceChannelPolicyError",
    "AdminMarketplaceResourceNotFoundError",
    "AdminMarketplaceTransitionError",
]
