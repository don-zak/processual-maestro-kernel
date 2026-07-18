"""Three-level supervision permission model for the admin area."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

OWNER_SUPERVISOR = "owner_supervisor"
OPERATIONS_SUPERVISOR = "operations_supervisor"
REVIEW_SUPERVISOR = "review_supervisor"

SUPERVISION_LEVELS = (
    OWNER_SUPERVISOR,
    OPERATIONS_SUPERVISOR,
    REVIEW_SUPERVISOR,
)

SUPERVISOR_SESSION_ISSUE_SCOPE = "admin:supervisor_sessions:issue"
SUPERVISOR_SESSION_REVOKE_SCOPE = "admin:supervisor_sessions:revoke"
SUPERVISOR_SESSION_READ_SCOPE = "admin:supervisor_sessions:read"

CLIENTS_READ_SCOPE = "admin:clients:read"
CLIENTS_CONTEXT_SCOPE = "admin:clients:context"
CLIENTS_STATUS_REVIEW_SCOPE = "admin:clients:status_review"
CLIENTS_STATUS_DECIDE_SCOPE = "admin:clients:status_decide"
CLIENTS_DRAFT_SCOPE = "admin:clients:draft"
CLIENTS_RESPOND_SCOPE = "admin:clients:respond"

USAGE_READ_SCOPE = "admin:usage:read"
QUOTA_READ_SCOPE = "admin:quota:read"
QUOTA_WRITE_SCOPE = "admin:quota:write"

PROVIDERS_READ_SCOPE = "admin:providers:read"
PROVIDERS_TEST_SCOPE = "admin:providers:test"
PROVIDERS_WRITE_SCOPE = "admin:providers:write"

API_KEYS_READ_SCOPE = "admin:api_keys:read"
API_KEYS_WRITE_SCOPE = "admin:api_keys:write"
API_KEYS_REVOKE_SCOPE = "admin:api_keys:revoke"

SYSTEM_READ_SCOPE = "admin:system:read"
SYSTEM_WRITE_SCOPE = "admin:system:write"

AUDIT_READ_SCOPE = "admin:audit:read"
AUDIT_WRITE_SCOPE = "admin:audit:write"
AUDIT_EXPORT_SCOPE = "admin:audit:export"

RBAC_READ_SCOPE = "admin:rbac:read"
RBAC_WRITE_SCOPE = "admin:rbac:write"


_OWNER_SCOPES = frozenset(
    {
        SUPERVISOR_SESSION_ISSUE_SCOPE,
        SUPERVISOR_SESSION_REVOKE_SCOPE,
        SUPERVISOR_SESSION_READ_SCOPE,
        CLIENTS_READ_SCOPE,
        CLIENTS_CONTEXT_SCOPE,
        CLIENTS_STATUS_REVIEW_SCOPE,
        CLIENTS_STATUS_DECIDE_SCOPE,
        CLIENTS_DRAFT_SCOPE,
        CLIENTS_RESPOND_SCOPE,
        USAGE_READ_SCOPE,
        QUOTA_READ_SCOPE,
        QUOTA_WRITE_SCOPE,
        PROVIDERS_READ_SCOPE,
        PROVIDERS_TEST_SCOPE,
        PROVIDERS_WRITE_SCOPE,
        API_KEYS_READ_SCOPE,
        API_KEYS_WRITE_SCOPE,
        API_KEYS_REVOKE_SCOPE,
        SYSTEM_READ_SCOPE,
        SYSTEM_WRITE_SCOPE,
        AUDIT_READ_SCOPE,
        AUDIT_WRITE_SCOPE,
        AUDIT_EXPORT_SCOPE,
        RBAC_READ_SCOPE,
        RBAC_WRITE_SCOPE,
    }
)

_OPERATIONS_SCOPES = frozenset(
    {
        CLIENTS_READ_SCOPE,
        CLIENTS_CONTEXT_SCOPE,
        CLIENTS_STATUS_REVIEW_SCOPE,
        CLIENTS_STATUS_DECIDE_SCOPE,
        CLIENTS_DRAFT_SCOPE,
        CLIENTS_RESPOND_SCOPE,
        USAGE_READ_SCOPE,
        QUOTA_READ_SCOPE,
        PROVIDERS_READ_SCOPE,
        PROVIDERS_TEST_SCOPE,
        API_KEYS_READ_SCOPE,
        SYSTEM_READ_SCOPE,
        AUDIT_READ_SCOPE,
    }
)

_REVIEW_SCOPES = frozenset(
    {
        CLIENTS_READ_SCOPE,
        CLIENTS_CONTEXT_SCOPE,
        CLIENTS_STATUS_REVIEW_SCOPE,
        CLIENTS_DRAFT_SCOPE,
        USAGE_READ_SCOPE,
        QUOTA_READ_SCOPE,
        AUDIT_READ_SCOPE,
    }
)

SUPERVISION_SCOPE_MATRIX = {
    OWNER_SUPERVISOR: _OWNER_SCOPES,
    OPERATIONS_SUPERVISOR: _OPERATIONS_SCOPES,
    REVIEW_SUPERVISOR: _REVIEW_SCOPES,
}


def _clean_scope(value: object) -> str:
    return str(value or "").strip().lower()


def _clean_level(value: object) -> str:
    return str(value or "").strip().lower()


def scopes_for_supervision_level(level: object) -> frozenset[str]:
    """Return the default scopes granted to a fixed supervision level."""
    return SUPERVISION_SCOPE_MATRIX.get(_clean_level(level), frozenset())


def can_issue_supervisor_session_key(level: object) -> bool:
    """Only the owner supervisor can issue supervisor session keys."""
    return _clean_level(level) == OWNER_SUPERVISOR


def _iter_explicit_scopes(user: Mapping[str, object]) -> Iterable[str]:
    raw_scopes = user.get("supervision_scopes") or user.get("scopes") or []
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]

    if not isinstance(raw_scopes, Iterable):
        return ()

    return (_clean_scope(scope) for scope in raw_scopes)


def can_use_supervision_scope(user: Mapping[str, object], scope: object) -> bool:
    """Return whether a supervision user has a level or explicit scope grant."""
    requested = _clean_scope(scope)
    if not requested:
        return False

    level_scopes = scopes_for_supervision_level(user.get("supervision_level"))
    explicit_scopes = set(_iter_explicit_scopes(user))

    return requested in level_scopes or requested in explicit_scopes


def require_supervision_scope(user: Mapping[str, object], scope: object) -> None:
    """Raise PermissionError unless the user has the requested supervision scope."""
    if can_use_supervision_scope(user, scope):
        return
    raise PermissionError(f"Missing supervision scope: {_clean_scope(scope)}")


def safe_supervision_permission_matrix() -> dict[str, tuple[str, ...]]:
    """Return a deterministic, secret-free permission matrix for UI/docs/tests."""
    return {
        level: tuple(sorted(scopes))
        for level, scopes in SUPERVISION_SCOPE_MATRIX.items()
    }
