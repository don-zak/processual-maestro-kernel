from __future__ import annotations

from typing import Any

from sqlalchemy.exc import DBAPIError, IntegrityError

from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConcurrencyError,
    AdminMarketplaceConflictError,
    AdminMarketplaceDuplicateReferenceError,
    AdminMarketplacePersistenceError,
)

UNIQUE_VIOLATION_SQLSTATE = "23505"
SERIALIZATION_FAILURE_SQLSTATE = "40001"
DEADLOCK_DETECTED_SQLSTATE = "40P01"

CONCURRENCY_SQLSTATES = frozenset(
    {
        SERIALIZATION_FAILURE_SQLSTATE,
        DEADLOCK_DETECTED_SQLSTATE,
    }
)


def extract_sqlstate(error: DBAPIError) -> str | None:
    """Extract a PostgreSQL SQLSTATE without depending on one driver."""

    original = error.orig

    sqlstate = getattr(original, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate:
        return sqlstate

    pgcode = getattr(original, "pgcode", None)
    if isinstance(pgcode, str) and pgcode:
        return pgcode

    return None


def extract_constraint_name(
    error: DBAPIError,
) -> str | None:
    """Extract the violated constraint name when supplied by the driver."""

    diagnostic: Any = getattr(error.orig, "diag", None)
    if diagnostic is None:
        return None

    constraint_name = getattr(
        diagnostic,
        "constraint_name",
        None,
    )

    if isinstance(constraint_name, str) and constraint_name:
        return constraint_name

    return None


def translate_database_error(
    error: DBAPIError,
) -> AdminMarketplacePersistenceError:
    """Translate SQLAlchemy DBAPI failures to stable marketplace errors."""

    sqlstate = extract_sqlstate(error)
    constraint_name = extract_constraint_name(error)

    if sqlstate == UNIQUE_VIOLATION_SQLSTATE:
        detail = _constraint_detail(constraint_name)

        return AdminMarketplaceDuplicateReferenceError(f"Admin Marketplace duplicate reference{detail}.")

    if sqlstate in CONCURRENCY_SQLSTATES:
        return AdminMarketplaceConcurrencyError("Admin Marketplace concurrent transaction conflict.")

    if isinstance(error, IntegrityError):
        detail = _constraint_detail(constraint_name)

        return AdminMarketplaceConflictError(f"Admin Marketplace integrity conflict{detail}.")

    return AdminMarketplaceConflictError("Admin Marketplace database conflict.")


def _constraint_detail(
    constraint_name: str | None,
) -> str:
    if constraint_name is None:
        return ""

    return f" ({constraint_name})"


__all__ = [
    "CONCURRENCY_SQLSTATES",
    "DEADLOCK_DETECTED_SQLSTATE",
    "SERIALIZATION_FAILURE_SQLSTATE",
    "UNIQUE_VIOLATION_SQLSTATE",
    "extract_constraint_name",
    "extract_sqlstate",
    "translate_database_error",
]
