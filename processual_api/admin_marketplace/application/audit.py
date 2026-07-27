from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from processual_api.admin_marketplace.authority import (
    PLATFORM_ADMIN_AUTHORITY,
    AdminMarketplaceAuthorityContext,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
)


def state_digest(
    value: Mapping[str, Any] | None,
) -> str | None:
    if value is None:
        return None

    encoded = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def build_audit_record(
    *,
    authority: AdminMarketplaceAuthorityContext,
    correlation_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    reason_code: str,
    previous_state: Mapping[str, Any] | None = None,
    new_state: Mapping[str, Any] | None = None,
    metadata: Mapping[str, str] | None = None,
    occurred_at: datetime | None = None,
    event_id: uuid.UUID | None = None,
) -> AdminMarketAuditRecord:
    timestamp = occurred_at or datetime.now(UTC)

    if timestamp.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware.")

    return AdminMarketAuditRecord(
        id=event_id or uuid.uuid4(),
        event_ref=f"audit-{uuid.uuid4().hex}",
        occurred_at=timestamp,
        actor_user_id=authority.user_id,
        actor_session_id=authority.session_id,
        platform_authority=PLATFORM_ADMIN_AUTHORITY,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason_code=reason_code,
        correlation_id=correlation_id,
        previous_state_digest=state_digest(previous_state),
        new_state_digest=state_digest(new_state),
        metadata_json=dict(metadata or {}),
    )


__all__ = [
    "build_audit_record",
    "state_digest",
]
