"""Soft-delete/archive controls for External Evaluation grant cards.

Archiving is intentionally not a hard delete. Active authority is revoked first,
while the grant record and execution/audit evidence remain durable and reviewable.
Archived grants are omitted from the default Admin grant list so the page does
not grow indefinitely.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    active_evaluation_key_count,
    load_evaluation_authority_state,
    revoke_evaluation_authority_grant,
    save_evaluation_authority_state,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_grants,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
    safe_evaluation_grant,
)

from . import settings as settings_module


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("sub") or current_user.get("user_id") or "default")


async def _require_admin(request: Request, current_user: dict[str, Any]) -> None:
    await require_active_platform_admin(current_user, request)


def _authority_error(exc: EvaluationAuthorityError) -> HTTPException:
    if str(exc) == "evaluation_grant_not_found":
        return HTTPException(status_code=404, detail="Evaluation grant not found.")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Shared Evaluation authority is unavailable.",
    )


@settings_module.router.get("/admin/evaluation-grants/visible", response_model=dict)
async def list_visible_evaluation_grants(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Return non-archived grants only; durable archived records remain server-side."""

    await _require_admin(request, current_user)
    owner_id = _owner_user_id(current_user)
    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        if str(exc) == "evaluation_authority_state_missing":
            return {
                "status": "ready",
                "grants": [],
                "grant_count": 0,
                "archived_grant_count": 0,
                "authority_store": "postgresql_shared",
                "subscription_required": False,
                "registration_required": False,
                "commercial_quota_required": False,
            }
        raise _authority_error(exc) from exc

    items: list[dict[str, Any]] = []
    archived_count = 0
    for grant in evaluation_grants(raw):
        if grant.get("archived_at"):
            archived_count += 1
            continue
        refresh_evaluation_grant_status(grant)
        item = safe_evaluation_grant(grant)
        try:
            item["active_key_count"] = await active_evaluation_key_count(
                owner_id,
                item["grant_id"],
            )
        except EvaluationAuthorityError as exc:
            raise _authority_error(exc) from exc
        items.append(item)

    return {
        "status": "ready",
        "grants": items,
        "grant_count": len(items),
        "archived_grant_count": archived_count,
        "authority_store": "postgresql_shared",
        "archive_semantics": "soft_delete_preserves_audit",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/archive",
    response_model=dict,
)
async def archive_evaluation_grant(
    grant_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Revoke active authority, then remove the grant from the default Admin list."""

    await _require_admin(request, current_user)
    owner_id = _owner_user_id(current_user)
    now = datetime.now(UTC).isoformat()

    try:
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise _authority_error(exc) from exc

    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Evaluation grant not found.")
    if grant.get("archived_at"):
        return {
            "status": "archived",
            "grant_id": grant_id,
            "archived_at": grant.get("archived_at"),
            "revoked_key_count": 0,
            "historical_audit_preserved": True,
        }

    try:
        revoked_keys = await revoke_evaluation_authority_grant(owner_id, grant_id)
        # Reload after the transactional revoke so the archive flag is applied to
        # the latest authoritative grant state rather than a stale pre-revoke copy.
        raw = await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        raise _authority_error(exc) from exc

    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Evaluation grant not found.")
    grant["archived_at"] = now
    grant["archived_by"] = str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "platform_admin"
    )
    raw[EVALUATION_GRANTS_STORAGE_KEY] = evaluation_grants(raw)[-500:]
    try:
        await save_evaluation_authority_state(owner_id, raw)
    except EvaluationAuthorityError as exc:
        raise _authority_error(exc) from exc

    return {
        "status": "archived",
        "grant_id": grant_id,
        "archived_at": now,
        "revoked_key_count": revoked_keys,
        "historical_audit_preserved": True,
        "production_allowed": False,
    }


__all__ = ["archive_evaluation_grant", "list_visible_evaluation_grants"]
