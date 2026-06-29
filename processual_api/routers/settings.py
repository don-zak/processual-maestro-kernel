"""User settings routes - LLM providers, notifications, preferences and connection tests."""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.security import _pbkdf2_hash_api_key, generate_api_key, get_current_user, hash_api_key
from ..dependencies import file_lock
from ..schemas.settings import (
    GeneralSettings,
    LLMProviderConfig,
    NotificationSettings,
    SettingsResponse,
    SubscriptionInfo,
    TestConnectionResult,
)

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
    with file_lock(path):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


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

    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key is required")

    known_providers = {"openai", "anthropic", "gemini", "deepseek", "opencode"}
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


@router.get("/api-keys", response_model=list[dict])
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    keys = raw.get("api_keys", [])

    visible_keys = []
    for key in keys:
        if key.get("status") == "revoked" or key.get("revoked_at"):
            continue

        visible_keys.append({
            "id": key.get("id", ""),
            "prefix": key.get("prefix", ""),
            "status": key.get("status", "enabled"),
            "scopes": key.get("scopes", []),
            "created_at": key.get("created_at", ""),
            "last_used_at": key.get("last_used_at"),
            "usage_count": key.get("usage_count", 0),
            "expires_at": key.get("expires_at"),
        })

    return visible_keys


@router.post("/api-keys", response_model=dict)
async def create_api_key(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    client_id = current_user.get("client_id") or user_id

    raw = _load_raw(user_id)
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

    keys.append({
        "id": key_id,
        "user_id": user_id,
        "client_id": client_id,
        "prefix": prefix,
        "hashed": hashed,
        "scopes": DEFAULT_API_KEY_SCOPES,
        "status": "enabled",
        "created_at": created_at,
        "last_used_at": None,
        "usage_count": 0,
        "expires_at": None,
        "revoked_at": None,
    })

    raw["api_keys"] = keys
    _save_raw(user_id, raw)

    return {
        "api_key": raw_key,
        "id": key_id,
        "prefix": prefix,
        "status": "enabled",
        "scopes": DEFAULT_API_KEY_SCOPES,
        "created_at": created_at,
    }


@router.delete("/api-keys/{key_id}", response_model=dict)
async def delete_api_key(key_id: str, current_user: dict = Depends(get_current_user)):
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
