"""Supervisor review state for customer Enterprise qualification drafts.

The review workflow deliberately supports read and revision-request boundaries
only. Reasons are fixed identifiers, not free text, so the settings store cannot
become a secret-bearing support channel. Sandbox approval remains a separate
privileged evidence decision and production/runtime activation stay out of scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from processual_api.integrations.enterprise_qualification_drafts import (
    DRAFT_STORAGE_KEY,
    safe_qualification_draft,
)

REVIEW_STORAGE_KEY = "enterprise_sandbox_qualification_review"
REVISION_REASON_CODES = frozenset(
    {
        "missing_customer_inputs",
        "profile_needs_clarification",
        "scope_needs_clarification",
        "security_evidence_required",
        "other_review_required",
    }
)


def _timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def safe_qualification_review(raw: dict[str, Any]) -> dict[str, Any] | None:
    value = raw.get(REVIEW_STORAGE_KEY)
    if not isinstance(value, dict):
        return None
    status = str(value.get("status") or "")
    reason_code = str(value.get("reason_code") or "")
    if status != "revision_requested" or reason_code not in REVISION_REASON_CODES:
        return None
    revision = value.get("draft_revision")
    if not isinstance(revision, int) or revision < 1:
        return None
    return {
        "status": "revision_requested",
        "reason_code": reason_code,
        "draft_revision": revision,
        "reviewed_at": str(value.get("reviewed_at") or ""),
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def request_qualification_revision(
    raw: dict[str, Any],
    *,
    reason_code: str,
    reviewer_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a submitted draft to draft state with a fixed safe reason code."""

    normalized_reason = str(reason_code or "").strip().lower()
    if normalized_reason not in REVISION_REASON_CODES:
        raise ValueError("unsupported qualification revision reason code")
    reviewer = str(reviewer_id or "").strip()
    if not reviewer:
        raise ValueError("reviewer identity is required")

    draft = safe_qualification_draft(raw)
    if draft is None:
        raise ValueError("valid qualification draft is required")
    if draft["draft_status"] != "pending_review":
        raise ValueError("qualification draft is not pending review")

    stored = raw.get(DRAFT_STORAGE_KEY)
    if not isinstance(stored, dict):  # pragma: no cover - guarded by safe read
        raise ValueError("valid qualification draft is required")
    timestamp = _timestamp(now)
    next_revision = int(draft["revision"]) + 1
    stored["status"] = "draft"
    stored["revision"] = next_revision
    stored["updated_at"] = timestamp
    stored.pop("submitted_at", None)
    raw[REVIEW_STORAGE_KEY] = {
        "status": "revision_requested",
        "reason_code": normalized_reason,
        "draft_revision": next_revision,
        "reviewer_id": reviewer,
        "reviewed_at": timestamp,
    }

    review = safe_qualification_review(raw)
    if review is None:  # pragma: no cover - defensive invariant
        raise ValueError("qualification review could not be rebuilt")
    return review


__all__ = [
    "REVIEW_STORAGE_KEY",
    "REVISION_REASON_CODES",
    "request_qualification_revision",
    "safe_qualification_review",
]
