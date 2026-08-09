"""Safe persistence primitives for Enterprise sandbox qualification drafts.

Only catalog identifiers and lifecycle metadata are stored. Readback is rebuilt
through the current server-side qualification contract so stale or corrupted
identifiers fail closed. Security approvals, credential values, runtime
activation, and production activation are never persisted by this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.integrations.enterprise_sandbox_qualification import (
    build_customer_sandbox_qualification,
)

DRAFT_STORAGE_KEY = "enterprise_sandbox_qualification_draft"
DRAFT_SCHEMA_VERSION = 1
_ALLOWED_STATUSES = {"draft", "pending_review"}


def _timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _stored_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    value = raw.get(DRAFT_STORAGE_KEY)
    return value if isinstance(value, dict) else None


def _revision(entry: dict[str, Any] | None) -> int:
    if not entry:
        return 0
    value = entry.get("revision")
    return value if isinstance(value, int) and value >= 0 else 0


def _profile_ordered_input_ids(
    profile_id: str,
    provided_input_ids: list[str],
) -> list[str]:
    """Persist validated inputs in the credential profile's contract order."""

    profile = get_credential_profile(profile_id)
    provided = set(provided_input_ids)
    return [
        input_id
        for input_id in profile.required_customer_inputs
        if input_id in provided
    ]


def _rebuild_qualification(entry: dict[str, Any]) -> dict[str, Any]:
    profile_id = entry.get("credential_profile_id")
    requested_scope_ids = entry.get("requested_scope_ids")
    provided_input_ids = entry.get("provided_input_ids")
    if not isinstance(profile_id, str):
        raise ValueError("stored qualification draft profile is invalid")
    if not isinstance(requested_scope_ids, list) or not all(
        isinstance(item, str) for item in requested_scope_ids
    ):
        raise ValueError("stored qualification draft scopes are invalid")
    if not isinstance(provided_input_ids, list) or not all(
        isinstance(item, str) for item in provided_input_ids
    ):
        raise ValueError("stored qualification draft inputs are invalid")
    return build_customer_sandbox_qualification(
        credential_profile_id=profile_id,
        requested_scope_ids=requested_scope_ids,
        provided_input_ids=provided_input_ids,
    )


def safe_qualification_draft(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Return a current-catalog safe draft payload or fail closed to no draft."""

    entry = _stored_entry(raw)
    if entry is None:
        return None
    try:
        qualification = _rebuild_qualification(entry)
    except (KeyError, ValueError):
        return None

    status = str(entry.get("status") or "draft")
    if status not in _ALLOWED_STATUSES:
        return None

    return {
        **qualification,
        "persisted": True,
        "draft_status": status,
        "revision": _revision(entry),
        "created_at": str(entry.get("created_at") or ""),
        "updated_at": str(entry.get("updated_at") or ""),
        "submitted_at": (
            str(entry.get("submitted_at") or "")
            if status == "pending_review"
            else None
        ),
        "security_controls_approved": 0,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def save_qualification_draft(
    raw: dict[str, Any],
    *,
    credential_profile_id: str,
    requested_scope_ids: list[str],
    provided_input_ids: list[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and store an identifiers-only draft, returning its safe readback."""

    qualification = build_customer_sandbox_qualification(
        credential_profile_id=credential_profile_id,
        requested_scope_ids=requested_scope_ids,
        provided_input_ids=provided_input_ids,
    )
    profile_id = str(qualification["credential_profile_id"])
    stored_input_ids = _profile_ordered_input_ids(
        profile_id,
        list(qualification["provided_input_ids"]),
    )
    existing = _stored_entry(raw)
    timestamp = _timestamp(now)
    created_at = (
        str(existing.get("created_at") or timestamp)
        if existing is not None
        else timestamp
    )
    raw[DRAFT_STORAGE_KEY] = {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": "draft",
        "revision": _revision(existing) + 1,
        "credential_profile_id": profile_id,
        "requested_scope_ids": list(qualification["requested_scope_ids"]),
        "provided_input_ids": stored_input_ids,
        "created_at": created_at,
        "updated_at": timestamp,
    }
    payload = safe_qualification_draft(raw)
    if payload is None:  # pragma: no cover - defensive invariant
        raise ValueError("qualification draft could not be rebuilt")
    return payload


def submit_qualification_draft(
    raw: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Move an existing valid draft to supervised review without approving it."""

    entry = _stored_entry(raw)
    if entry is None:
        raise ValueError("qualification draft is required before submission")
    qualification = _rebuild_qualification(entry)
    profile_id = str(qualification["credential_profile_id"])
    stored_input_ids = _profile_ordered_input_ids(
        profile_id,
        list(qualification["provided_input_ids"]),
    )
    timestamp = _timestamp(now)
    raw[DRAFT_STORAGE_KEY] = {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": "pending_review",
        "revision": _revision(entry) + 1,
        "credential_profile_id": profile_id,
        "requested_scope_ids": list(qualification["requested_scope_ids"]),
        "provided_input_ids": stored_input_ids,
        "created_at": str(entry.get("created_at") or timestamp),
        "updated_at": timestamp,
        "submitted_at": timestamp,
    }
    payload = safe_qualification_draft(raw)
    if payload is None:  # pragma: no cover - defensive invariant
        raise ValueError("qualification draft could not be submitted")
    return payload


__all__ = [
    "DRAFT_SCHEMA_VERSION",
    "DRAFT_STORAGE_KEY",
    "safe_qualification_draft",
    "save_qualification_draft",
    "submit_qualification_draft",
]
