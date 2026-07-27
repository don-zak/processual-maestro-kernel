from __future__ import annotations


class AdminMarketplacePersistenceError(RuntimeError):
    """Base error for Admin Marketplace persistence failures."""


class AdminMarketplaceNotFoundError(AdminMarketplacePersistenceError):
    """A requested Admin Marketplace record does not exist."""


class AdminMarketplaceConflictError(AdminMarketplacePersistenceError):
    """A persistence operation conflicts with the current stored state."""


class AdminMarketplaceConcurrencyError(AdminMarketplaceConflictError):
    """A concurrent mutation invalidated the requested operation."""


class AdminMarketplaceDuplicateReferenceError(AdminMarketplaceConflictError):
    """A unique commercial reference already exists."""


class AdminMarketplaceImmutableRecordError(AdminMarketplaceConflictError):
    """An immutable commercial record was targeted for mutation."""


__all__ = [
    "AdminMarketplaceConcurrencyError",
    "AdminMarketplaceConflictError",
    "AdminMarketplaceDuplicateReferenceError",
    "AdminMarketplaceImmutableRecordError",
    "AdminMarketplaceNotFoundError",
    "AdminMarketplacePersistenceError",
]
