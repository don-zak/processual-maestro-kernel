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


class DirectCommerceUnavailableError(AdminMarketplaceError):
    """Raised when a fail-closed direct-commerce gate is not satisfied."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Direct commerce is unavailable.")


class DirectCommerceConflictError(AdminMarketplaceError):
    """Raised when an idempotent order request conflicts with stored state."""


class ContractCompletionConflictError(AdminMarketplaceError):
    """Raised when contract completion conflicts with the order state."""


class CommercialOrderNotFoundError(AdminMarketplaceError):
    """Raised when an authenticated customer cannot access an order."""


class PaymentEvidenceNotFoundError(AdminMarketplaceError):
    """Raised when payment evidence cannot be accessed."""


class PaymentEvidenceConflictError(AdminMarketplaceError):
    """Raised when a payment report conflicts with trusted order state."""


class PaymentVerificationConflictError(AdminMarketplaceError):
    """Raised when an administrator decision conflicts with stored state."""


class PaymentReconciliationConflictError(AdminMarketplaceError):
    """Raised when a reconciliation action conflicts with trusted state."""


class SubscriptionActivationNotReadyError(AdminMarketplaceError):
    """Raised when a verified order does not satisfy every activation gate."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("Subscription activation is not ready.")


class SubscriptionActivationConflictError(AdminMarketplaceError):
    """Raised when an activation request conflicts with stored state."""


__all__ = [
    "AdminMarketplaceAuditSafetyError",
    "AdminMarketplaceAuthorityDeniedError",
    "AdminMarketplaceError",
    "AdminMarketplaceStepUpRequiredError",
    "CommercialOrderNotFoundError",
    "ContractCompletionConflictError",
    "DirectCommerceConflictError",
    "DirectCommerceUnavailableError",
    "PaymentDestinationConflictError",
    "PaymentDestinationNotFoundError",
    "PaymentEvidenceConflictError",
    "PaymentEvidenceNotFoundError",
    "PaymentVerificationConflictError",
    "PaymentReconciliationConflictError",
    "SubscriptionActivationConflictError",
    "SubscriptionActivationNotReadyError",
]
