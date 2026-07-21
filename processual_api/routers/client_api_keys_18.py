"""Client self-service sandbox API keys for eligible enterprise integrations.

This module attaches routes to the existing settings router. It deliberately
allows only server-catalogued, client-visible, read-only sandbox profiles.
Production, runtime connector approval, arbitrary scopes, and cross-client
issuance remain unavailable.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import (
    _pbkdf2_hash_api_key,
    generate_api_key,
    get_current_user,
    hash_api_key,
)
from processual_api.integrations.api_key_operational_profiles import (
    get_api_key_operational_profile,
)

from . import settings as settings_module


class ClientSandboxKeyCreate(BaseModel):
    profile_id: str = Field(min_length=1, max_length=120)
    label: str = Field(default="Institution sandbox", min_length=1, max_length=120)
    purpose: str = Field(default="Approved sandbox integration", min_length=1, max_length=240)
    expires_in_days: int = Field(default=30, ge=1, le=90)


class ClientSandboxKeyRotate(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=90)


def _identity(current_user: dict) -> tuple[str, str]:
    user_id = str(current_user.get("user_id") or current_user.get("sub") or "default")
    client_id = str(current_user.get("client_id") or user_id)
    return user_id, client_id


def _eligible_plan(user_id: str, client_id: str, raw: dict, current_user: dict) -> str:
    plan_id = settings_module._resolve_client_api_key_integration_plan_id(
        user_id,
        raw,
        current_user,
    )
    if not settings_module._allows_client_api_key_integration(plan_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client sandbox API keys require an eligible Enterprise Integration plan.",
        )
    if not client_id:
        raise HTTPException(status_code=403, detail="Client identity is required.")
    return plan_id


def _safe_profile(profile_id: str) -> dict:
    try:
        profile = get_api_key_operational_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Unknown operational profile.") from exc

    allowed = (
        profile.get("client_visible") is True
        and profile.get("environment") == "sandbox"
        and profile.get("read_only") is True
        and profile.get("write_allowed") is False
        and profile.get("restricted_allowed") is False
        and profile.get("production_allowed") is False
        and profile.get("runtime_connector_approved") is False
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This profile requires supervisor approval and cannot be issued by self-service.",
        )
    return profile


def _hash(raw_key: str) -> str:
    try:
        return hash_api_key(raw_key)
    except RuntimeError as exc:
        if "bcrypt" not in str(exc).lower():
            raise
        return _pbkdf2_hash_api_key(raw_key)


def _active_self_service_keys(raw: dict, client_id: str) -> list[dict]:
    keys = raw.get("api_keys", [])
    if not isinstance(keys, list):
        return []
    return [
        key
        for key in keys
        if isinstance(key, dict)
        and key.get("self_service_sandbox") is True
        and str(key.get("client_id") or "") == client_id
        and key.get("status") not in {"revoked", "disabled", "expired"}
        and not key.get("revoked_at")
    ]


def _safe_key(key: dict) -> dict:
    return {
        "key_id": str(key.get("id") or ""),
        "prefix": str(key.get("prefix") or ""),
        "status": str(key.get("status") or "enabled"),
        "profile_id": str(key.get("operational_profile_id") or ""),
        "label": str(key.get("label") or ""),
        "purpose": str(key.get("purpose") or ""),
        "environment": "sandbox",
        "scopes": list(key.get("scopes") or []),
        "created_at": str(key.get("created_at") or ""),
        "expires_at": str(key.get("expires_at") or ""),
        "last_used_at": key.get("last_used_at"),
        "usage_count": int(key.get("usage_count", 0) or 0),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def _issue(
    raw: dict,
    *,
    client_id: str,
    user_id: str,
    plan_id: str,
    profile: dict,
    label: str,
    purpose: str,
    expires_in_days: int,
) -> tuple[dict, str]:
    active = _active_self_service_keys(raw, client_id)
    if len(active) >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum active self-service sandbox keys reached. Revoke or rotate an existing key.",
        )

    raw_key = generate_api_key()
    now = datetime.now(UTC)
    key_id = f"csbk_{secrets.token_hex(8)}"
    entry = {
        "id": key_id,
        "user_id": user_id,
        "client_id": client_id,
        "prefix": raw_key[:12] + "...",
        "hashed": _hash(raw_key),
        "scopes": list(profile.get("allowed_scopes") or []),
        "profile": str(profile.get("base_key_profile") or "service_integration"),
        "category": "client_sandbox_integration",
        "role": "client",
        "operational_profile_id": str(profile.get("profile_id") or ""),
        "label": label,
        "purpose": purpose,
        "issued_to": client_id,
        "created_by_admin_role": None,
        "self_service_sandbox": True,
        "environment": "sandbox",
        "plan_id": plan_id,
        "quota_scope": "evaluation",
        "quota_limit": settings_module.quota_limit_for_plan(plan_id, "evaluation"),
        "quota_used": 0,
        "quota_rejected_count": 0,
        "status": "enabled",
        "created_at": now.isoformat(),
        "last_used_at": None,
        "usage_count": 0,
        "expires_at": (now + timedelta(days=expires_in_days)).isoformat(),
        "revoked_at": None,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }
    keys = raw.get("api_keys", [])
    if not isinstance(keys, list):
        keys = []
    keys.append(entry)
    raw["api_keys"] = keys
    return entry, raw_key


@settings_module.router.get("/client/api-keys", response_model=dict)
async def list_client_sandbox_api_keys(current_user: dict = Depends(get_current_user)):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
    keys = [_safe_key(key) for key in _active_self_service_keys(raw, client_id)]
    return {
        "status": "ready",
        "plan_id": plan_id,
        "environment": "sandbox",
        "key_count": len(keys),
        "keys": keys,
        "max_active_keys": 3,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.post("/client/api-keys", response_model=dict, status_code=201)
async def create_client_sandbox_api_key(
    body: ClientSandboxKeyCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
    profile = _safe_profile(body.profile_id)
    entry, raw_key = _issue(
        raw,
        client_id=client_id,
        user_id=user_id,
        plan_id=plan_id,
        profile=profile,
        label=body.label,
        purpose=body.purpose,
        expires_in_days=body.expires_in_days,
    )
    settings_module._save_raw(user_id, raw)
    return {
        "status": "created",
        "api_key": raw_key,
        "visible_once": True,
        "key": _safe_key(entry),
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.post("/client/api-keys/{key_id}/rotate", response_model=dict)
async def rotate_client_sandbox_api_key(
    key_id: str,
    body: ClientSandboxKeyRotate,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
    target = next((key for key in _active_self_service_keys(raw, client_id) if key.get("id") == key_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Client sandbox API key not found.")
    profile = _safe_profile(str(target.get("operational_profile_id") or ""))
    target["status"] = "revoked"
    target["revoked_at"] = datetime.now(UTC).isoformat()
    entry, raw_key = _issue(
        raw,
        client_id=client_id,
        user_id=user_id,
        plan_id=plan_id,
        profile=profile,
        label=str(target.get("label") or "Institution sandbox"),
        purpose=str(target.get("purpose") or "Approved sandbox integration"),
        expires_in_days=body.expires_in_days,
    )
    entry["rotated_from_key_id"] = key_id
    settings_module._save_raw(user_id, raw)
    return {
        "status": "rotated",
        "api_key": raw_key,
        "visible_once": True,
        "revoked_key_id": key_id,
        "key": _safe_key(entry),
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


@settings_module.router.delete("/client/api-keys/{key_id}", response_model=dict)
async def revoke_client_sandbox_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    _eligible_plan(user_id, client_id, raw, current_user)
    target = next((key for key in _active_self_service_keys(raw, client_id) if key.get("id") == key_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Client sandbox API key not found.")
    target["status"] = "revoked"
    target["revoked_at"] = datetime.now(UTC).isoformat()
    settings_module._save_raw(user_id, raw)
    return {
        "status": "revoked",
        "key_id": key_id,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }
