"""Authoritative External Evaluation Access administration.

This replaces the legacy evaluation-grant registrations with the original
standalone contract: platform-super-admin issuance, no signup/subscription or
commercial-plan quota dependency, explicit endpoint/task authority, one-time
credential disclosure, expiry/revocation, and production-disabled runtime use.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import (
    _pbkdf2_hash_api_key,
    generate_api_key,
    get_current_user,
    hash_api_key,
)
from processual_api.integrations.api_key_access_policy import (
    get_api_key_access_policy,
    list_api_key_access_policies,
)
from processual_api.integrations.integration_task_catalog import (
    get_integration_task,
    task_catalog_payload,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    EVALUATION_GRANTS_STORAGE_KEY,
    evaluation_grants,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
    safe_evaluation_grant,
    validate_evaluation_grant,
)

from . import settings as settings_module
from . import settings_admin_evaluation_grants as legacy_evaluation

PILOT_DEFAULT_SCOPES = [
    "read:health",
    "read:adapters",
    "read:governor",
    "run:analyze",
    "run:govern",
    "read:reports",
    "run:evaluation",
]


class EvaluationEndpointSelection(BaseModel):
    method: str = Field(min_length=3, max_length=10)
    path: str = Field(min_length=1, max_length=300)


class EvaluationGrantCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=160)
    user_id: str | None = Field(default=None, min_length=1, max_length=160)
    issued_to: str = Field(min_length=1, max_length=240)
    purpose: str = Field(min_length=10, max_length=500)
    allowed_task_ids: list[str] = Field(min_length=1, max_length=24)
    allowed_endpoints: list[EvaluationEndpointSelection] = Field(min_length=1, max_length=32)
    allowed_scopes: list[str] = Field(
        default_factory=lambda: list(PILOT_DEFAULT_SCOPES),
        min_length=1,
        max_length=16,
    )
    max_requests: int = Field(default=200, ge=1, le=5000)
    expires_in_days: int = Field(default=14, ge=1, le=90)


class EvaluationKeyIssue(BaseModel):
    label: str = Field(
        default="External evaluation access",
        min_length=1,
        max_length=160,
    )


def _owner_user_id(current_user: dict[str, Any]) -> str:
    return str(
        current_user.get("sub")
        or current_user.get("user_id")
        or "default"
    )


def _actor(current_user: dict[str, Any]) -> tuple[str, str]:
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
    scopes: list[str] = []
    seen: set[str] = set()
    for value in values:
        scope = str(value or "").strip().lower()
        if not scope or scope in seen:
            continue
        if scope.startswith("admin:") or scope in {"*", "admin:*", "admin:dangerous"}:
            raise HTTPException(
                status_code=422,
                detail="Evaluation grants cannot include administrative scopes.",
            )
        seen.add(scope)
        scopes.append(scope)
    if not scopes:
        raise HTTPException(status_code=422, detail="At least one evaluation scope is required.")
    return scopes


def _endpoint_selection(
    values: list[EvaluationEndpointSelection],
    allowed_scopes: list[str],
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    scope_set = {str(scope).strip().lower() for scope in allowed_scopes}
    for value in values:
        method = value.method.strip().upper()
        path = value.path.strip()
        key = (method, path)
        if key in seen:
            continue
        policy = get_api_key_access_policy(method, path)
        if policy is None:
            raise HTTPException(
                status_code=422,
                detail=f"Endpoint is not eligible for evaluation access: {method} {path}",
            )
        if policy.production_allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Production endpoint cannot enter evaluation access: {method} {path}",
            )
        required_scopes = set(policy.required_scopes)
        if not required_scopes.issubset(scope_set):
            raise HTTPException(
                status_code=422,
                detail=f"Endpoint scope derivation mismatch: {method} {path}",
            )
        seen.add(key)
        selected.append({"method": method, "path": path})
    if not selected:
        raise HTTPException(
            status_code=422,
            detail="At least one eligible evaluation endpoint is required.",
        )
    return selected


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
            raise HTTPException(status_code=422, detail=f"Unknown evaluation task: {task_id}") from exc
        if not task.sandbox_allowed or task.auto_execute_production:
            raise HTTPException(
                status_code=422,
                detail=f"Task is not eligible for evaluation access: {task_id}",
            )
        seen_tasks.add(task_id)
        selected.append(task_id)
        for scope_id in task.required_scope_ids:
            if scope_id not in seen_scopes:
                seen_scopes.add(scope_id)
                task_scopes.append(scope_id)
    if not selected:
        raise HTTPException(
            status_code=422,
            detail="At least one canonical evaluation task is required.",
        )
    return selected, task_scopes


def _linked_key_count(raw: dict[str, Any], grant_id: str) -> int:
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


def _access_catalog_payload() -> list[dict[str, Any]]:
    return [
        {
            "method": policy.method,
            "path": policy.path,
            "task_id": policy.task_id,
            "capability": policy.capability,
            "operation_class": policy.operation_class,
            "required_scopes": list(policy.required_scopes),
            "operational_profile_ids": list(policy.operational_profile_ids),
            "production_allowed": False,
        }
        for policy in list_api_key_access_policies()
        if not policy.production_allowed
    ]


async def _require_platform_admin(
    request: Request,
    current_user: dict[str, Any],
) -> None:
    await require_active_platform_admin(current_user, request)


@settings_module.router.get("/admin/evaluation-grants/authority", response_model=dict)
async def evaluation_grant_authority(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    return {
        "authorized": True,
        "authority": "platform_admin",
        "exclusive_super_administrator": True,
        "subscription_required": False,
        "commercial_quota_required": False,
    }


@settings_module.router.get("/admin/evaluation-grants/access-catalog", response_model=dict)
async def evaluation_access_catalog(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    endpoints = _access_catalog_payload()
    return {
        "status": "ready",
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
        "default_scopes": list(PILOT_DEFAULT_SCOPES),
        "execution_mode": EVALUATION_EXECUTION_MODE,
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "production_allowed": False,
    }


@settings_module.router.get("/admin/evaluation-grants/task-catalog", response_model=dict)
async def evaluation_task_catalog(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    return {
        **task_catalog_payload(),
        "selection_authority": "integration_task_catalog",
        "subscription_required": False,
        "evaluation_key_binding_supported": True,
    }


@settings_module.router.post("/admin/evaluation-grants", response_model=dict, status_code=201)
async def create_evaluation_grant(
    body: EvaluationGrantCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grants = evaluation_grants(raw)
    now = datetime.now(UTC)
    actor, role = _actor(current_user)
    scopes = _safe_scopes(body.allowed_scopes)
    endpoints = _endpoint_selection(body.allowed_endpoints, scopes)
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
        "allowed_endpoints": endpoints,
        "allowed_scopes": scopes,
        "max_requests": int(body.max_requests),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=body.expires_in_days)).isoformat(),
        "approved_by": actor,
        "approved_by_role": role,
        "revoked_at": None,
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "entitlement_source": "admin_evaluation_grant",
        "task_authority_source": "integration_task_catalog",
        "endpoint_authority_source": "canonical_runtime_access_policy",
        "execution_mode": EVALUATION_EXECUTION_MODE,
        "real_runtime_execution": True,
        "production_allowed": False,
    }
    grants.append(grant)
    raw[EVALUATION_GRANTS_STORAGE_KEY] = grants[-500:]
    settings_module._save_raw(owner_user_id, raw)
    return {"status": "created", "grant": safe_evaluation_grant(grant)}


@settings_module.router.get("/admin/evaluation-grants", response_model=dict)
async def list_evaluation_grants(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grants = evaluation_grants(raw)
    changed = False
    items: list[dict[str, Any]] = []
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
        "registration_required": False,
        "commercial_quota_required": False,
    }


@settings_module.router.post(
    "/admin/evaluation-grants/{grant_id}/issue-key",
    response_model=dict,
    status_code=201,
)
async def issue_evaluation_key(
    grant_id: str,
    body: EvaluationKeyIssue,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
    owner_user_id = _owner_user_id(current_user)
    raw = settings_module._load_raw(owner_user_id)
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="Evaluation grant not found.")

    scopes = list(grant.get("allowed_scopes") or [])
    endpoints = list(grant.get("allowed_endpoints") or [])
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
            requested_endpoints=endpoints,
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
        "allowed_endpoints": endpoints,
        "allowed_task_ids": task_ids,
        "task_scope_ids": task_scope_ids,
        "task_authority_source": "integration_task_catalog",
        "endpoint_authority_source": "canonical_runtime_access_policy",
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
        "registration_required": False,
        "commercial_quota_required": False,
        "execution_mode": EVALUATION_EXECUTION_MODE,
        "real_runtime_execution": True,
        "quota_limit": max_requests,
        "evaluation_request_limit": max_requests,
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
            "allowed_endpoints": endpoints,
            "allowed_task_ids": task_ids,
            "task_scope_ids": task_scope_ids,
            "execution_mode": EVALUATION_EXECUTION_MODE,
            "real_runtime_execution": True,
            "evaluation_request_limit": max_requests,
            "expires_at": entry["expires_at"],
            "subscription_required": False,
            "registration_required": False,
            "commercial_quota_required": False,
            "production_allowed": False,
        },
        "onboarding_usage": {
            "header": "X-API-Key",
            "example_endpoint": endpoints[0]["path"] if endpoints else "/health/live",
        },
    }


@settings_module.router.delete("/admin/evaluation-grants/{grant_id}", response_model=dict)
async def revoke_evaluation_grant(
    grant_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_platform_admin(request, current_user)
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
    if not isinstance(keys, list):
        keys = []
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


def _matches(route: Any, path: str, method: str) -> bool:
    methods = getattr(route, "methods", set()) or set()
    return isinstance(route, APIRoute) and route.path == path and method in methods


_REPLACED = {
    ("/settings/admin/evaluation-grants/task-catalog", "GET"),
    ("/settings/admin/evaluation-grants", "POST"),
    ("/settings/admin/evaluation-grants", "GET"),
    ("/settings/admin/evaluation-grants/{grant_id}/issue-key", "POST"),
    ("/settings/admin/evaluation-grants/{grant_id}", "DELETE"),
}

_original_new_routes = [
    route
    for route in settings_module.router.routes
    if isinstance(route, APIRoute)
    and (
        route.endpoint in {
            evaluation_grant_authority,
            evaluation_access_catalog,
            evaluation_task_catalog,
            create_evaluation_grant,
            list_evaluation_grants,
            issue_evaluation_key,
            revoke_evaluation_grant,
        }
    )
]
settings_module.router.routes[:] = [
    route
    for route in settings_module.router.routes
    if not any(_matches(route, path, method) for path, method in _REPLACED)
]
settings_module.router.routes.extend(_original_new_routes)


__all__ = [
    "EvaluationEndpointSelection",
    "EvaluationGrantCreate",
    "EvaluationKeyIssue",
    "PILOT_DEFAULT_SCOPES",
]
