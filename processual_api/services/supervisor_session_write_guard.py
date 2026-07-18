from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from processual_api.supervisor_session_keys import validate_supervisor_session_key


class SupervisorSessionWriteGuardError(PermissionError):
    """Safe structured denial for supervisor-session-protected writes."""

    def __init__(
        self,
        *,
        error: str,
        detail: str,
        session_present: bool,
        session_validated: bool,
        required_scopes: list[str],
        session_key_id: str = "",
        provided_scopes: list[str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.error = error
        self.detail = detail
        self.session_present = session_present
        self.session_validated = session_validated
        self.required_scopes = required_scopes
        self.session_key_id = session_key_id
        self.provided_scopes = provided_scopes or []


def supervisor_session_write_guard_store_path() -> Path:
    """Return the configured supervisor session store path."""

    configured = os.environ.get("PMK_SUPERVISOR_SESSION_KEYS_PATH", "").strip()

    if configured:
        return Path(configured)

    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "supervisor_session_keys.json"
    )


def supervisor_session_header_value(request: Any) -> str:
    """Read canonical supervisor session header with legacy compatibility."""

    headers = getattr(request, "headers", {})

    return str(
        headers.get("X-Supervisor-Session-Key")
        or headers.get("X-Admin-Supervisor-Session")
        or ""
    ).strip()


def _normalize_scopes(raw_scopes: Any) -> set[str]:
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]

    if not isinstance(raw_scopes, (list, tuple, set)):
        return set()

    return {
        str(scope).strip()
        for scope in raw_scopes
        if str(scope or "").strip()
    }


def _normalize_allowed_scopes(allowed_scopes: Any) -> set[str]:
    return _normalize_scopes(allowed_scopes)


def _scope_allows(provided_scopes: set[str], allowed_scopes: set[str]) -> bool:
    if "*" in provided_scopes or "admin:*" in provided_scopes:
        return True

    if "*" in allowed_scopes or "admin:*" in allowed_scopes:
        return bool(provided_scopes)

    return bool(provided_scopes.intersection(allowed_scopes))


def require_validated_supervisor_write_session(
    request: Any,
    allowed_scopes: set[str] | list[str] | tuple[str, ...],
    *,
    guard_name: str,
    store_path: Path | None = None,
) -> dict[str, object]:
    """Validate a supervisor session and return safe actor metadata only."""

    normalized_allowed = _normalize_allowed_scopes(allowed_scopes)
    required_scopes = sorted(normalized_allowed)
    raw_session = supervisor_session_header_value(request)

    if not raw_session:
        raise SupervisorSessionWriteGuardError(
            error="supervisor_session_required",
            detail=f"Supervisor session required for {guard_name}",
            session_present=False,
            session_validated=False,
            required_scopes=required_scopes,
        )

    try:
        safe_session = validate_supervisor_session_key(
            store_path or supervisor_session_write_guard_store_path(),
            raw_session,
        )
    except (PermissionError, OSError, ValueError, TypeError) as exc:
        raise SupervisorSessionWriteGuardError(
            error="invalid_supervisor_session",
            detail=f"Invalid supervisor session for {guard_name}",
            session_present=True,
            session_validated=False,
            required_scopes=required_scopes,
        ) from exc

    provided_scopes = _normalize_scopes(safe_session.get("scopes"))
    session_key_id = str(safe_session.get("session_key_id") or "").strip()

    if (
        not session_key_id
        or not _scope_allows(provided_scopes, normalized_allowed)
    ):
        raise SupervisorSessionWriteGuardError(
            error="supervisor_scope_required",
            detail=f"Supervisor scope does not allow {guard_name}",
            session_present=True,
            session_validated=True,
            required_scopes=required_scopes,
            session_key_id=session_key_id,
            provided_scopes=sorted(provided_scopes),
        )

    return {
        "session_present": True,
        "session_validated": True,
        "session_key_id": session_key_id,
        "provided_scopes": sorted(provided_scopes),
        "required_scopes": required_scopes,
    }
