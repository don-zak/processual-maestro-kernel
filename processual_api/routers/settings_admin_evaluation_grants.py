"""Supervisor-governed evaluation access outside paid subscription flows."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import (
    _pbkdf2_hash_api_key,
    generate_api_key,
    get_current_user,
    hash_api_key,
)
from processual_api.integrations.integration_task_catalog import (
    get_integration_task,
    task_catalog_payload,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_grants,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
    safe_evaluation_grant,
    validate_evaluation_grant,
)

from . import settings as settings_module

PILOT_DEFAULT_SCOPES = [
    "read:health",
    "read:governor",
    "run:analyze",
    "run:govern",
    "read:reports",
]


class EvaluationGrantCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=160)
    user_id: str | None = Field(default=None, min_length=1, max_length=160)
    issued_to: str = Field(min_length=1, max_length=240)
    purpose: str = Field(min_length=10, max_length=500)
    allowed_task_ids: list[str] = Field(min_length=1, max_length=24)
    allowed_scopes: list[str] = Field(
        default_factory=lambda: list(PILOT_DEFAULT_SCOPES),
        min_length=1,
        max_length=16,
    )
    max_requests: int = Field(default=100, ge=1, le=10000)
    expires_in_days: int = Field(default=14, ge=1, le=90)


class EvaluationKeyIssue(BaseModel):
    label: str = Field(
        default="External evaluation access",
        min_length=1,
        max_length=160,
    )


def _owner_user_id(current_user: dict) -> str:
    return str(
        current_user.get("sub")
        or current_user.get("user_id")
        or "default"
    )


def _actor(current_user: dict) -> tuple[str, str]:
    actor = str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "super_admin"
    )
    return actor, "platform_admin"


def _hash_key(raw_key: str) -> str:
    try:
        return hash_api_key(raw_key)
    except RuntimeError as exc:
        if "bcrypt" not in str(exc).lower():
            raise
        return _pbkdf2_hash_api_key(raw_key)


def _safe_scopes(values: list[str]) -> list[str]:
    scopes = []
    seen = set()
    for value in values:
        scope = str(value or "").strip()
        if not scope or scope in seen:
            continue
        if scope.startswith("admin:") or scope in {
            "*",
            "admin:*",
            "admin:dangerous",
        }:
            raise HTTPException(
                status_code=422,
                detail="Evaluation grants cannot include administrative scopes.",
            )
        seen.add(scope)
        scopes.append(scope)
    if not scopes:
        raise HTTPException(
            status_code=422,
            detail="At least one evaluation scope is required.",
        )
    return scopes


def _task_selection(task_ids: list[str]) -> tuple[list[str], list[str]]:
    selected: list[str] = []
    task_scopes: list[str] = []
    seen_tasks: set[str] = set()
    seen_scopes: set[str] = set()

    for raw_task_id in task_ids:
        task_id = str(raw_task_id or "").strip().lower()
        if not task_id or task_id in seen_tasks:
            continue
        try:
            task = get_integration_task(task_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown evaluation task: {task_id}",
            ) from exc
        if not task.sandbox_allowed or task.auto_execute_production:
            raise HTTPException(
                status_code=422,
                detail=f"Task is not eligible for evaluation access: {task_id}",
            )
        seen_tasks.add(task_id)
        selected.append(task_id)
        for scope_id in task.required_scope_ids:
            if scope_id in seen_scopes:
                continue
            seen_scopes.add(scope_id)
            task_scopes.append(scope_id)

    if not selected:
        raise HTTPException(
            status_code=422,
            detail="At least one canonical evaluation task is required.",
        )
    return selected, task_scopes


def _linked_key_count(raw: dict, grant_id: str) -> int:
    keys = raw.get("api_keys", [])
    if not isinstance(keys, list):
        return 0
    return sum(
        1
        for key in keys
        if isinstance(key, dict)
        and str(key.get("evaluation_grant_id") or "") == grant_id
        and key.get("status") not in {"revoked", "disabled", "expired"}
        and not key.get("revoked_at")
    )


@settings_module.router.get(
    "/admin/evaluation-grants/authority",
    response_model=dict,
)
async def evaluation_grant_authority(
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    return {
        "authorized": True,
        "authority": "platform_admin",
        "exclusive_super_administrator": True,
    }


@settings_module.router.get(
    "/admin/evaluation-grants/task-catalog",
    response_model=dict,
)
async def evaluation_task_catalog(
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    payload = task_catalog_payload()
    return {
        **payload,
        "selection_authority": "integration_task_catalog",
        "subscription_required": False,
        "evaluation_key_binding_supported": True,
    }


@settings_module.router.post(
    "/admin/evaluation-grants",
    response_model=dict,
    status_code=201,
)
async def create_evaluation_grant(
    body: EvaluationGrantCreate,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grants = evaluation_grants(raw)
    now = datetime.now(UTC)
    actor, role = _actor(current_user)
    scopes = _safe_scopes(body.allowed_scopes)
    task_ids, task_scope_ids = _task_selection(body.allowed_task_ids)

    grant = {
        "grant_id": f"eval_{secrets.token_hex(8)}",
        "status": "active",
        "client_id": body.client_id.strip(),
        "user_id": str(body.user_id or body.client_id).strip(),
        "issued_to": body.issued_to.strip(),
        "purpose": body.purpose.strip(),
        "allowed_task_ids": task_ids,
        "task_scope_ids": task_scope_ids,
        "allowed_scopes": scopes,
        "max_requests": int(body.max_requests),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=body.expires_in_days)).isoformat(),
        "approved_by": actor,
        "approved_by_role": role,
        "revoked_at": None,
        "subscription_required": False,
        "entitlement_source": "admin_evaluation_grant",
        "task_authority_source": "integration_task_catalog",
        "production_allowed": False,
    }
    grants.append(grant)
    raw[EVALUATION_GRANTS_STORAGE_KEY] = grants[-500:]
    settings_module._save_raw(owner_user_id, raw)
    return {"status": "created", "grant": safe_evaluation_grant(grant)}


@settings_module.router.get(
    "/admin/evaluation-grants",
    response_model=dict,
)
async def list_evaluation_grants(
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grants = evaluation_grants(raw)
    changed = False
    items = []
    for grant in grants:
        before = str(grant.get("status") or "")
        refresh_evaluation_grant_status(grant)
        changed = changed or before != str(grant.get("status") or "")
        item = safe_evaluation_grant(grant)
        item["active_key_count"] = _linked_key_count(raw, item["grant_id"])
        items.append(item)
    if changed:
        raw[EVALUATION_GRANTS_STORAGE_KEY] = grants
        settings_module._save_raw(owner_user_id, raw)
    return {
        "status": "ready",
        "grants": items,
        "grant_count": len(items),
        "subscription_required": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/issue-key",
    response_model=dict,
    status_code=201,
)
async def issue_evaluation_key(
    grant_id: str,
    body: EvaluationKeyIssue,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Evaluation grant not found.")

    scopes = list(grant.get("allowed_scopes") or [])
    task_ids = list(grant.get("allowed_task_ids") or [])
    task_scope_ids = list(grant.get("task_scope_ids") or [])
    client_id = str(grant.get("client_id") or "")
    max_requests = int(grant.get("max_requests", 0) or 0)
    try:
        validate_evaluation_grant(
            raw,
            grant_id=grant_id,
            client_id=client_id,
            requested_scopes=scopes,
            requested_task_ids=task_ids,
            quota_limit=max_requests,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if _linked_key_count(raw, grant_id) >= 3:
        raise HTTPException(
            status_code=409,
            detail="Maximum active evaluation keys reached for this grant.",
        )

    raw_key = generate_api_key()
    now = datetime.now(UTC).isoformat()
    key_id = f"evalkey_{secrets.token_hex(8)}"
    entry = {
        "id": key_id,
        "user_id": str(grant.get("user_id") or client_id),
        "client_id": client_id,
        "prefix": raw_key[:12] + "...",
        "hashed": _hash_key(raw_key),
        "scopes": scopes,
        "allowed_task_ids": task_ids,
        "task_scope_ids": task_scope_ids,
        "task_authority_source": "integration_task_catalog",
        "profile": "client",
        "category": "pilot_client",
        "role": "client",
        "label": body.label.strip(),
        "purpose": str(grant.get("purpose") or ""),
        "issued_to": str(grant.get("issued_to") or client_id),
        "created_by_admin_role": "platform_admin",
        "evaluation_grant_id": grant_id,
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "plan_id": "Starter",
        "quota_policy": {
            "id": "evaluation_grant",
            "name": "Admin Evaluation Grant",
            "source": "manual",
            "quotas": {"evaluation": max_requests},
        },
        "quota_scope": "evaluation",
        "quota_limit": max_requests,
        "quota_limit_override": max_requests,
        "quota_used": 0,
        "quota_rejected_count": 0,
        "status": "enabled",
        "created_at": now,
        "last_used_at": None,
        "usage_count": 0,
        "expires_at": str(grant.get("expires_at") or ""),
        "revoked_at": None,
        "production_allowed": False,
    }
    keys = raw.get("api_keys", [])
    if not isinstance(keys, list):
        keys = []
    keys.append(entry)
    raw["api_keys"] = keys
    settings_module._save_raw(owner_user_id, raw)

    return {
        "status": "created",
        "api_key": raw_key,
        "visible_once": True,
        "key": {
            "key_id": key_id,
            "prefix": entry["prefix"],
            "category": "pilot_client",
            "client_id": client_id,
            "evaluation_grant_id": grant_id,
            "scopes": scopes,
            "allowed_task_ids": task_ids,
            "task_scope_ids": task_scope_ids,
            "task_authority_source": "integration_task_catalog",
            "quota_limit": max_requests,
            "expires_at": entry["expires_at"],
            "subscription_required": False,
            "production_allowed": False,
        },
        "onboarding_usage": {
            "header": "X-API-Key",
            "example_endpoint": "/adapters/status",
        },
    }


@settings_module.router.delete(
    "/admin/evaluation-grants/{grant_id}",
    response_model=dict,
)
async def revoke_evaluation_grant(
    grant_id: str,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Evaluation grant not found.")

    now = datetime.now(UTC).isoformat()
    grant["status"] = "revoked"
    grant["revoked_at"] = now
    revoked_keys = 0
    keys = raw.get("api_keys", [])
    if isinstance(keys, list):
        for key in keys:
            if not isinstance(key, dict):
                continue
            if str(key.get("evaluation_grant_id") or "") != grant_id:
                continue
            if key.get("status") in {"revoked", "disabled", "expired"} or key.get("revoked_at"):
                continue
            key["status"] = "revoked"
            key["revoked_at"] = now
            key["revocation_reason"] = "evaluation_grant_revoked"
            revoked_keys += 1

    raw[EVALUATION_GRANTS_STORAGE_KEY] = evaluation_grants(raw)
    raw["api_keys"] = keys
    settings_module._save_raw(owner_user_id, raw)
    return {
        "status": "revoked",
        "grant_id": grant_id,
        "revoked_at": now,
        "revoked_key_count": revoked_keys,
    }
