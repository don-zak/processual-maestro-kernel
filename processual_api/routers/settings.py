"""User settings routes - LLM providers, notifications, preferences and connection tests."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth.security import _pbkdf2_hash_api_key, generate_api_key, get_current_user, hash_api_key, require_scope
from ..cgt_governor.adapters.provider_metadata import provider_ids
from ..dependencies import file_lock
from ..schemas.settings import (
    GeneralSettings,
    LLMProviderConfig,
    NotificationSettings,
    SettingsResponse,
    SubscriptionInfo,
    TestConnectionResult,
)
from ..services.plan_store import PLAN_POLICIES, get_plan_policy, quota_limit_for_plan, resolve_plan_id

try:
    from processual_kernel.security.crypto import decrypt_aes256_gcm, encrypt_aes256_gcm
    from processual_kernel.security.exceptions import DecryptionError

    _crypto_available = True
except ImportError:
    _crypto_available = False

router = APIRouter(prefix="/settings", tags=["settings"])
DEFAULT_API_KEY_SCOPES = [
    "read:health",
    "read:adapters",
    "read:governor",
    "run:analyze",
    "run:govern",
    "run:compare",
    "read:reports",
    "create:reports",
]
ADMIN_SETTINGS_SCOPE = "admin:settings"
CLIENT_KEY_PROFILE = "client"
DEFAULT_API_KEY_CATEGORY = "client_api"
API_KEY_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "client_api": {
        "role": "client",
        "scopes": DEFAULT_API_KEY_SCOPES,
    },
    "pilot_client": {
        "role": "client",
        "scopes": [
            "read:health",
            "read:governor",
            "run:analyze",
            "run:govern",
            "read:reports",
        ],
    },
    "external_partner": {
        "role": "partner",
        "scopes": ["read:health"],
    },
    "service_integration": {
        "role": "service",
        "scopes": ["read:health", "read:adapters", "read:governor", "run:govern"],
    },
    "billing_service": {
        "role": "service",
        "scopes": ["admin:billing:read", "admin:billing:write"],
    },
    "support_viewer": {
        "role": "support_admin",
        "scopes": ["admin:read", "admin:clients:read", "admin:usage:read"],
    },
    "ops_admin": {
        "role": "ops_admin",
        "scopes": [
            "admin:read",
            "admin:adapters:read",
            "admin:adapters:write",
            "admin:usage:read",
            "admin:health:read",
        ],
    },
    "billing_admin": {
        "role": "billing_admin",
        "scopes": [
            "admin:read",
            "admin:clients:read",
            "admin:clients:write",
            "admin:billing:read",
            "admin:billing:write",
            "admin:usage:read",
        ],
    },
    "security_admin": {
        "role": "security_admin",
        "scopes": [
            "admin:read",
            "admin:settings",
            "admin:api_keys:read",
            "admin:api_keys:write",
            "admin:api_keys:revoke",
            "admin:audit:read",
        ],
    },
    "owner_admin": {
        "role": "owner_admin",
        "scopes": ["admin:*", "admin:dangerous"],
    },
    "emergency_bootstrap": {
        "role": "owner_admin",
        "scopes": ["admin:read"],
    },
}


def _clean_api_key_scopes(
    requested_scopes: list[str] | None,
    default_scopes: list[str],
) -> list[str]:
    scopes = [
        str(scope).strip()
        for scope in requested_scopes or []
        if str(scope).strip()
    ]
    return scopes or list(default_scopes)


def _resolve_api_key_profile(
    body: ApiKeyCreateRequest | None,
) -> tuple[str, str, list[str]]:
    category = DEFAULT_API_KEY_CATEGORY
    if body and body.category:
        category = body.category.strip()

    profile = API_KEY_PROFILE_DEFAULTS.get(category)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown API key category: {category}",
        )

    default_role = str(profile["role"])
    default_scopes = list(profile["scopes"])

    role = body.role.strip() if body and body.role else default_role
    scopes = _clean_api_key_scopes(body.scopes if body else None, default_scopes)

    return category, role, scopes


def _current_admin_role(current_user: dict) -> str:
    return str(
        current_user.get("admin_role")
        or current_user.get("role")
        or current_user.get("token_role")
        or "admin"
    )


class ApiKeyPlanUpdate(BaseModel):
    plan_id: str


class ApiKeyQuotaUpdate(BaseModel):
    quota_limit_override: int | None = Field(default=None, ge=-1)


class ApiKeyCreateRequest(BaseModel):
    client_id: str | None = Field(default=None, min_length=1)
    user_id: str | None = Field(default=None, min_length=1)
    plan_id: str | None = Field(default=None, min_length=1)
    label: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    role: str | None = Field(default=None, min_length=1)
    scopes: list[str] | None = None
    quota_limit_override: int | None = Field(default=None, ge=-1)
    expires_at: str | None = Field(default=None, min_length=1)
    purpose: str | None = Field(default=None, min_length=1)
    issued_to: str | None = Field(default=None, min_length=1)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CRYPTO_KEY = os.environ.get("PROCESSUAL_CRYPTO_KEY_B64", "")


def _settings_path(user_id: str) -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / f"settings_{user_id}.json"


def _load_raw(user_id: str) -> dict[str, Any]:
    path = _settings_path(user_id)
    if path.exists():
        with file_lock(path):
            try:
                return json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def _save_raw(user_id: str, data: dict[str, Any]):
    path = _settings_path(user_id)
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    backup_path = path.with_suffix(path.suffix + ".bak")

    with file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            if path.exists():
                shutil.copy2(path, backup_path)
            tmp_path.replace(path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    general = data.get("general", {})
    llm_provider = data.get("llm_provider", {})
    notifications = data.get("notifications", {})
    subscription = data.get("subscription", {})

    return {
        "general": {
            "language": general.get("language", "en"),
            "refresh_interval": general.get("refresh_interval", 30),
            "timezone": general.get("timezone", "UTC"),
        },
        "llm_provider": {
            "configured": llm_provider.get("configured", False),
            "provider": llm_provider.get("provider", ""),
            "model": llm_provider.get("model", ""),
            "last_tested": llm_provider.get("last_tested"),
        },
        "notifications": {
            "discord_webhook": notifications.get("discord_webhook", ""),
            "alert_level": notifications.get("alert_level", "warning"),
        },
        "subscription": {
            "plan": subscription.get("plan", "Starter"),
            "status": subscription.get("status", "active"),
            "renews_at": subscription.get("renews_at"),
            "seats": subscription.get("seats", 1),
            "max_seats": subscription.get("max_seats", 1),
        },
    }


def _encrypt_api_key(api_key: str, user_id: str) -> str | None:
    if not _crypto_available or not _CRYPTO_KEY:
        return None
    try:
        envelope = encrypt_aes256_gcm(api_key.encode("utf-8"), _CRYPTO_KEY, key_id=user_id)
        return json.dumps({
            "algorithm": envelope.algorithm,
            "key_id": envelope.key_id,
            "nonce_b64": envelope.nonce_b64,
            "aad_b64": envelope.aad_b64,
            "ciphertext_b64": envelope.ciphertext_b64,
            "plaintext_sha3_256": envelope.plaintext_sha3_256,
            "ciphertext_sha3_256": envelope.ciphertext_sha3_256,
            "schema_version": envelope.schema_version,
            "created_at": envelope.created_at,
        })
    except Exception:
        return None


def _decrypt_api_key(stored: str) -> str | None:
    if not _crypto_available or not _CRYPTO_KEY:
        return None
    try:
        from processual_kernel.security.crypto import CryptoEnvelope
        data = json.loads(stored)
        envelope = CryptoEnvelope(
            algorithm=data["algorithm"],
            key_id=data["key_id"],
            nonce_b64=data["nonce_b64"],
            aad_b64=data["aad_b64"],
            ciphertext_b64=data["ciphertext_b64"],
            plaintext_sha3_256=data["plaintext_sha3_256"],
            ciphertext_sha3_256=data["ciphertext_sha3_256"],
            schema_version=data.get("schema_version", "processual-crypto-envelope-2.0.0"),
            created_at=data.get("created_at", ""),
        )
        plaintext = decrypt_aes256_gcm(envelope, _CRYPTO_KEY)
        return plaintext.decode("utf-8")
    except (DecryptionError, KeyError, json.JSONDecodeError):
        return None


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    merged = _merge_defaults(raw)
    return SettingsResponse(
        general=GeneralSettings(**merged["general"]),
        llm_provider=merged["llm_provider"],
        notifications=NotificationSettings(**merged["notifications"]),
        subscription=SubscriptionInfo(**merged["subscription"]),
    )


@router.put("/general", response_model=GeneralSettings)
async def update_general(body: GeneralSettings, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    raw["general"] = body.model_dump()
    _save_raw(user_id, raw)
    return body


@router.put("/llm-provider", response_model=dict)
async def save_llm_provider(body: LLMProviderConfig, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)

    encrypted = _encrypt_api_key(body.api_key, user_id) if body.api_key else None
    raw["llm_provider"] = {
        "configured": bool(body.api_key and body.provider),
        "provider": body.provider,
        "model": body.model,
        "last_tested": raw.get("llm_provider", {}).get("last_tested"),
    }

    if encrypted:
        raw["llm_provider"]["encrypted_key"] = encrypted

    _save_raw(user_id, raw)

    return {
        "status": "saved",
        "provider": body.provider,
        "model": body.model or "",
        "configured": bool(body.api_key and body.provider),
    }


@router.delete("/llm-provider", response_model=dict)
async def clear_llm_provider(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    raw["llm_provider"] = {"configured": False, "provider": "", "model": ""}
    _save_raw(user_id, raw)
    return {"status": "cleared"}


@router.post("/llm-provider/test", response_model=TestConnectionResult)
async def test_llm_provider(body: LLMProviderConfig, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    provider = body.provider.lower()

    api_key = body.api_key
    if not api_key:
        raw = _load_raw(user_id)
        encrypted = raw.get("llm_provider", {}).get("encrypted_key")
        if encrypted:
            decrypted = _decrypt_api_key(encrypted)
            if decrypted:
                api_key = decrypted

    if not api_key and provider not in {"opencode", "generic_openai_compatible"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key is required")

    known_providers = provider_ids()
    if provider not in known_providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    start = time.time()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            if provider == "openai":
                res = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "anthropic":
                res = await client.get(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
            elif provider == "gemini":
                res = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
            elif provider == "deepseek":
                res = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "opencode":
                base_url = os.environ.get("OPENCODE_API_URL", "http://localhost:11434/v1")
                res = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                )
            elif provider == "openrouter":
                base_url = os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
                res = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "generic_openai_compatible":
                base_url = os.environ.get("GENERIC_OPENAI_API_URL", "").rstrip("/")
                if not base_url:
                    return TestConnectionResult(success=False, error="GENERIC_OPENAI_API_URL is required")
                res = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                )

            latency = (time.time() - start) * 1000

            if res.status_code == 200:
                return TestConnectionResult(success=True, latency_ms=round(latency, 1))
            else:
                return TestConnectionResult(
                    success=False,
                    error=f"HTTP {res.status_code}: Provider returned non-200",
                )

    except httpx.TimeoutException:
        return TestConnectionResult(success=False, error="Connection timed out after 10s")
    except Exception as e:
        return TestConnectionResult(success=False, error=str(e)[:200])


@router.put("/notifications", response_model=NotificationSettings)
async def update_notifications(body: NotificationSettings, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    raw["notifications"] = body.model_dump()
    _save_raw(user_id, raw)
    return body


@router.post("/notifications/test", response_model=dict)
async def test_notifications(body: NotificationSettings, current_user: dict = Depends(get_current_user)):
    if not body.discord_webhook:
        raise HTTPException(status_code=400, detail="Discord webhook URL is required")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                body.discord_webhook,
                json={"content": "[OK] Processual Maestro - Notification test successful"},
            )
            if res.status_code in (200, 204):
                return {"status": "sent"}
            return {"status": "error", "detail": f"HTTP {res.status_code}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:200])


def _load_billing_subscriptions() -> list[dict]:
    path = _DATA_DIR / "subscriptions.json"
    if path.exists():
        try:
            import json
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _compute_stage(sub: dict) -> str:
    from datetime import datetime
    status = sub.get("status", "active")
    if status == "active":
        return "active"
    if status in ("expired", "cancelled"):
        return "expired"

    created_str = sub.get("suspended_at") or sub.get("created_at", "")
    try:
        suspended_at = datetime.fromisoformat(created_str)
    except (ValueError, TypeError):
        return "grace"

    days_since = (datetime.now(UTC) - suspended_at).days
    if days_since <= 7:
        return "grace"
    elif days_since <= 90:
        return "suspended"
    else:
        return "expired"


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")

    # Check billing subscriptions first
    billing_subs = _load_billing_subscriptions()
    user_subs = [s for s in billing_subs if s.get("user_id") == user_id]
    if user_subs:
        latest = max(user_subs, key=lambda s: s.get("created_at", ""))
        stage = _compute_stage(latest)
        return SubscriptionInfo(
            plan=latest.get("plan", "Starter"),
            status=latest.get("status", "active"),
            stage=stage,
            renews_at=latest.get("renews_at"),
            seats=latest.get("seats", 1),
            max_seats=latest.get("max_seats", 1),
            payment_failures=latest.get("payment_failures", 0),
            suspended_at=latest.get("suspended_at"),
        )

    # Fall back to local settings
    raw = _load_raw(user_id)
    sub = raw.get("subscription", {})
    return SubscriptionInfo(
        plan=sub.get("plan", "Starter"),
        status=sub.get("status", "active"),
        stage=sub.get("stage", "active"),
        renews_at=sub.get("renews_at"),
        seats=sub.get("seats", 1),
        max_seats=sub.get("max_seats", 1),
        payment_failures=sub.get("payment_failures", 0),
        suspended_at=sub.get("suspended_at"),
    )

def _find_active_api_key_or_404(raw: dict, key_id: str) -> dict:
    for key in raw.get("api_keys", []):
        if key.get("id") != key_id:
            continue
        if key.get("status") == "revoked" or key.get("revoked_at"):
            break
        return key

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="API key not found",
    )


def _api_key_quota_summary(key: dict) -> dict:
    quota_policy = key.get("quota_policy", {})
    quota_policy_source = (
        quota_policy.get("source")
        if isinstance(quota_policy, dict)
        else None
    )
    quota_limit = key.get("quota_limit")

    return {
        "id": key.get("id", ""),
        "plan_id": key.get("plan_id"),
        "quota_scope": key.get("quota_scope") or "evaluation",
        "quota_limit": quota_limit,
        "quota_used": key.get("quota_used", 0),
        "quota_remaining": (
            max(int(quota_limit) - int(key.get("quota_used", 0)), 0)
            if isinstance(quota_limit, int) and quota_limit >= 0
            else None
        ),
        "quota_policy_source": quota_policy_source,
        "quota_limit_override": key.get("quota_limit_override"),
        "quota_rejected_count": key.get("quota_rejected_count", 0),
    }

@router.get("/plans", response_model=list[dict])
async def list_plans(current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE))):
    return [get_plan_policy(plan_id) for plan_id in PLAN_POLICIES.keys()]

@router.get("/api-keys", response_model=list[dict])
async def list_api_keys(current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE))):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    raw_keys = raw.get("api_keys", [])

    if isinstance(raw_keys, dict):
        keys = list(raw_keys.values())
    elif isinstance(raw_keys, list):
        keys = raw_keys
    else:
        keys = []

    visible_keys = []
    for key in keys:
        if not isinstance(key, dict):
            continue

        if key.get("status") == "revoked" or key.get("revoked_at"):
            continue

        visible_keys.append({
            "id": key.get("id", ""),
            "key_id": key.get("id", ""),
            "prefix": key.get("prefix", ""),
            "status": key.get("status", "enabled"),
            "category": key.get("category", DEFAULT_API_KEY_CATEGORY),
            "role": key.get("role", CLIENT_KEY_PROFILE),
            "profile": key.get("profile", CLIENT_KEY_PROFILE),
            "label": key.get("label"),
            "purpose": key.get("purpose"),
            "issued_to": key.get("issued_to"),
            "created_by_admin_role": key.get("created_by_admin_role"),
            "client_id": key.get("client_id"),
            "user_id": key.get("user_id"),
            "scopes": key.get("scopes", []),
            "created_at": key.get("created_at", ""),
            "last_used_at": key.get("last_used_at"),
            "usage_count": key.get("usage_count", 0),
            "plan_id": key.get("plan_id"),
            "quota_scope": key.get("quota_scope"),
            "quota_limit": key.get("quota_limit"),
            "quota_limit_override": key.get("quota_limit_override"),
            "quota_used": key.get("quota_used", 0),
            "quota_rejected_count": key.get("quota_rejected_count", 0),
            "expires_at": key.get("expires_at"),
            "revoked_at": key.get("revoked_at"),
        })

    return visible_keys


def _resolve_current_plan_id(user_id: str, raw: dict) -> str:
    billing_subs = _load_billing_subscriptions()
    user_subs = [s for s in billing_subs if s.get("user_id") == user_id]
    if user_subs:
        latest = max(user_subs, key=lambda s: s.get("created_at", ""))
        return resolve_plan_id(latest.get("plan_id") or latest.get("plan"))

    subscription = raw.get("subscription", {})
    return resolve_plan_id(subscription.get("plan_id") or subscription.get("plan", "Starter"))


@router.post("/api-keys", response_model=dict)
async def create_api_key(
    body: ApiKeyCreateRequest | None = None,
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):

    owner_user_id = current_user.get("sub", "default")
    requested_client_id = body.client_id if body else None
    requested_user_id = body.user_id if body else None
    category, role, scopes = _resolve_api_key_profile(body)
    created_by_admin_role = _current_admin_role(current_user)
    quota_limit_override = body.quota_limit_override if body else None
    expires_at = body.expires_at if body else None
    purpose = body.purpose if body else None
    issued_to = body.issued_to if body else None

    user_id = requested_user_id or requested_client_id or owner_user_id
    client_id = requested_client_id or current_user.get("client_id") or user_id

    raw = _load_raw(owner_user_id)
    keys = raw.get("api_keys", [])

    raw_key = generate_api_key()
    try:
        hashed = hash_api_key(raw_key)
    except RuntimeError as exc:
        if "bcrypt" not in str(exc).lower():
            raise
        hashed = _pbkdf2_hash_api_key(raw_key)

    key_id = secrets.token_hex(8)
    prefix = raw_key[:12] + "..."
    created_at = datetime.now(UTC).isoformat()
    requested_plan_id = body.plan_id if body and body.plan_id else None
    plan_id = resolve_plan_id(requested_plan_id) if requested_plan_id else _resolve_current_plan_id(owner_user_id, raw)

    if quota_limit_override is None:
        quota_policy = get_plan_policy(plan_id)
        quota_limit = quota_limit_for_plan(plan_id, "evaluation")
    else:
        quota_limit = int(quota_limit_override)
        quota_policy = {
            "id": "manual_override",
            "name": "Manual Quota Override",
            "source": "manual",
            "quotas": {
                "evaluation": quota_limit,
            },
        }

    profile = CLIENT_KEY_PROFILE if role == CLIENT_KEY_PROFILE else category

    keys.append({
        "id": key_id,
        "user_id": user_id,
        "client_id": client_id,
        "prefix": prefix,
        "hashed": hashed,
        "scopes": scopes,
        "profile": profile,
        "category": category,
        "role": role,
        "label": body.label if body and body.label else None,
        "purpose": purpose,
        "issued_to": issued_to,
        "created_by_admin_role": created_by_admin_role,
        "plan_id": plan_id,
        "quota_policy": quota_policy,
        "quota_scope": "evaluation",
        "quota_limit": quota_limit,
        "quota_limit_override": quota_limit_override,
        "quota_used": 0,
        "quota_reset_at": None,
        "status": "enabled",
        "created_at": created_at,
        "last_used_at": None,
        "usage_count": 0,
        "expires_at": expires_at,
        "revoked_at": None,
    })

    raw["api_keys"] = keys
    _save_raw(owner_user_id, raw)

    return {
        "api_key": raw_key,
        "id": key_id,
        "key_id": key_id,
        "plan_id": plan_id,
        "quota_policy": quota_policy,
        "quota_scope": "evaluation",
        "quota_limit": quota_limit,
        "quota_limit_override": quota_limit_override,
        "quota_used": 0,
        "prefix": prefix,
        "status": "enabled",
        "scopes": scopes,
        "profile": profile,
        "category": category,
        "role": role,
        "client_id": client_id,
        "user_id": user_id,
        "label": body.label if body and body.label else None,
        "purpose": purpose,
        "issued_to": issued_to,
        "created_by_admin_role": created_by_admin_role,
        "expires_at": expires_at,
        "onboarding_usage": {
            "header": "X-API-Key",
            "base_url": "http://127.0.0.1:8000",
            "example_endpoint": "/adapters/status",
        },
        "created_at": created_at,
    }


@router.patch("/api-keys/{key_id}/plan", response_model=dict)
async def update_api_key_plan(
    key_id: str,
    body: ApiKeyPlanUpdate,
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)

    key = _find_active_api_key_or_404(raw, key_id)

    plan_id = resolve_plan_id(body.plan_id)
    quota_scope = key.get("quota_scope") or "evaluation"
    quota_policy = get_plan_policy(plan_id)
    quota_limit = quota_limit_for_plan(plan_id, quota_scope)

    key["plan_id"] = plan_id
    key["quota_policy"] = quota_policy
    key["quota_scope"] = quota_scope
    key["quota_limit"] = quota_limit
    key.pop("quota_limit_override", None)

    raw["api_keys"] = raw.get("api_keys", [])
    _save_raw(user_id, raw)

    return {
        "status": "updated",
        "change": "plan",
        **_api_key_quota_summary(key),
    }


@router.patch("/api-keys/{key_id}/quota", response_model=dict)
async def update_api_key_quota(
    key_id: str,
    body: ApiKeyQuotaUpdate,
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)

    key = _find_active_api_key_or_404(raw, key_id)

    quota_scope = key.get("quota_scope") or "evaluation"
    plan_id = resolve_plan_id(
        key.get("plan_id")
        or key.get("plan")
        or raw.get("subscription", {}).get("plan_id")
        or raw.get("subscription", {}).get("plan")
        or "Starter"
    )

    if body.quota_limit_override is None:
        quota_policy = get_plan_policy(plan_id)
        quota_limit = quota_limit_for_plan(plan_id, quota_scope)

        key.pop("quota_limit_override", None)
        key["plan_id"] = plan_id
        key["quota_policy"] = quota_policy
        key["quota_limit"] = quota_limit
        key["quota_scope"] = quota_scope

        change = "quota_override_cleared"
    else:
        quota_limit = int(body.quota_limit_override)

        key["plan_id"] = plan_id
        key["quota_limit_override"] = quota_limit
        key["quota_policy"] = {
            "id": "manual_override",
            "name": "Manual Quota Override",
            "source": "manual",
            "quotas": {
                quota_scope: quota_limit,
            },
        }
        key["quota_limit"] = quota_limit
        key["quota_scope"] = quota_scope

        change = "quota_override_set"

    raw["api_keys"] = raw.get("api_keys", [])
    _save_raw(user_id, raw)

    return {
        "status": "updated",
        "change": change,
        **_api_key_quota_summary(key),
    }

@router.delete("/api-keys/{key_id}", response_model=dict)
async def delete_api_key(key_id: str, current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE))):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    keys = raw.get("api_keys", [])

    revoked = False
    now = datetime.now(UTC).isoformat()

    for key in keys:
        if key.get("id") == key_id:
            key["status"] = "revoked"
            key["revoked_at"] = now
            revoked = True
            break

    raw["api_keys"] = keys
    _save_raw(user_id, raw)

    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    return {"status": "revoked", "id": key_id, "revoked_at": now}
