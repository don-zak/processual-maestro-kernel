from __future__ import annotations


class AdminMarketplaceError(ValueError):
    """Base error for invalid Admin Marketplace contract state."""


class AdminMarketplaceAuthorityDeniedError(PermissionError):
    """Raised when an actor lacks exclusive marketplace authority."""


class AdminMarketplaceStepUpRequiredError(PermissionError):
    """Raised when a sensitive action lacks recent MFA step-up."""


class AdminMarketplaceAuditSafetyError(AdminMarketplaceError):
    """Raised when audit metadata contains prohibited sensitive material."""


class PaymentDestinationNotFoundError(AdminMarketplaceError):
    """Raised when a payment destination does not exist."""


class PaymentDestinationConflictError(AdminMarketplaceError):
    """Raised when a payment-destination transition conflicts with stored state."""


__all__ = [
    "AdminMarketplaceAuditSafetyError",
    "AdminMarketplaceAuthorityDeniedError",
    "AdminMarketplaceError",
    "AdminMarketplaceStepUpRequiredError",
    "PaymentDestinationConflictError",
    "PaymentDestinationNotFoundError",
]
