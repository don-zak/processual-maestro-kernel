"""User settings routes - LLM providers, notifications, preferences and connection tests."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.admin_audit_log import append_admin_audit_event, read_admin_audit_events

from ..auth.security import _pbkdf2_hash_api_key, generate_api_key, get_current_user, hash_api_key, require_scope
from ..billing.usage_pricing import (
    BILLING_POLICY,
    ENTERPRISE_INTEGRATION_PLANS,
    PROVIDER_COST_INCLUDED,
    allows_enterprise_integration,
    normalize_plan_id,
)
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
from ..services.admin_subscription_analytics import build_admin_subscription_analytics
from ..services.client_plan_source import (
    ClientRequestPlanApplyError,
    apply_verified_client_request_plan,
    supported_verified_plan,
)
from ..services.client_usage_summary import build_client_usage_summary
from ..services.plan_store import PLAN_POLICIES, get_plan_policy, quota_limit_for_plan, resolve_plan_id
from ..services.usage_log_store import summarize_usage_logs
from ..supervision_rbac import (
    CLIENTS_DRAFT_SCOPE,
    CLIENTS_RESPOND_SCOPE,
    CLIENTS_STATUS_DECIDE_SCOPE,
    CLIENTS_STATUS_REVIEW_SCOPE,
    OWNER_SUPERVISOR,
    require_supervision_scope,
)
from ..supervisor_session_keys import (
    issue_supervisor_session_key,
    list_supervisor_session_keys,
    revoke_supervisor_session_key,
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



CLIENT_REQUEST_TYPE_LABELS: dict[str, str] = {
    "enterprise_integration_upgrade": "Upgrade to Enterprise Integration",
    "integration_key_provisioning": "Request integration key provisioning",
    "integration_key_rotation": "Request integration key rotation",
    "integration_key_deactivation": "Request integration key deactivation",
    "provider_setup_help": "Provider setup help",
    "billing_usage_review": "Billing and usage review",
    "general_support": "General support",
}


class ClientRequestPayload(BaseModel):
    request_type: str = Field(default="general_support", min_length=1)
    requested_plan: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=10, max_length=2000)


class ClientProviderConnectionSetupPayload(BaseModel):
    provider: str = Field(min_length=1)
    provider_secret: str | None = Field(default=None, max_length=4096)
    model: str | None = Field(default=None, max_length=200)


CLIENT_PROVIDER_SECRET_OPTIONAL_PROVIDERS = {"opencode", "generic_openai_compatible"}


def _normalize_client_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    known_providers = provider_ids()
    if provider not in known_providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    return provider


def _client_request_type_options() -> list[dict[str, str]]:
    return [
        {"id": request_type, "label": label}
        for request_type, label in CLIENT_REQUEST_TYPE_LABELS.items()
    ]


def _normalize_client_request_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if normalized in CLIENT_REQUEST_TYPE_LABELS:
        return normalized
    return "general_support"

def _client_request_type_label(request_type: str | None) -> str:
    return CLIENT_REQUEST_TYPE_LABELS.get(
        str(request_type or "general_support"),
        "General support",
    )


def _client_request_short_id(request_id: str | None) -> str:
    value = str(request_id or "").strip()
    return value[:8] if value else "-"


def _client_request_summary(entry: dict[str, Any]) -> dict[str, Any]:
    request_id = str(entry.get("request_id") or entry.get("id") or "")
    request_type = str(entry.get("request_type") or "general_support")
    requested_plan = str(entry.get("requested_plan") or "")
    status_value = str(entry.get("status") or "pending")
    created_at = str(entry.get("created_at") or "")
    source = str(entry.get("source") or "client")
    message = str(entry.get("message") or "")
    message_preview = message[:120]
    if len(message) > 120:
        message_preview += "..."

    return {
        "id": request_id,
        "request_id": request_id,
        "short_id": _client_request_short_id(request_id),
        "request_type": request_type,
        "request_type_label": _client_request_type_label(request_type),
        "requested_plan": requested_plan,
        "status": status_value,
        "created_at": created_at,
        "source": source,
        "message_preview": message_preview,
        "supervisor_responses": _client_safe_supervisor_responses(entry),
    }


def _client_requests(raw: dict[str, Any]) -> list[dict[str, Any]]:
    requests = raw.get("client_requests", [])
    return requests if isinstance(requests, list) else []


@router.get("/client-requests", response_model=dict)
async def list_client_requests(current_user: dict = Depends(get_current_user)):
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    raw = _load_raw(user_id)
    requests = _client_requests(raw)

    summaries = [
        _client_request_summary(entry)
        for entry in requests
        if isinstance(entry, dict)
    ]
    summaries.sort(
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )
    latest = summaries[:10]
    status_counts: dict[str, int] = {}
    for item in summaries:
        item_status = str(item.get("status") or "pending")
        status_counts[item_status] = status_counts.get(item_status, 0) + 1

    return {
        "status": "ready",
        "request_count": len(summaries),
        "latest_count": len(latest),
        "status_counts": status_counts,
        "request_types": _client_request_type_options(),
        "latest_requests": latest,
        "message": "Client requests are ready for admin follow-up.",
    }




def _admin_client_requests_scopes(current_user: dict) -> set[str]:
    raw_scopes = current_user.get("scopes") or current_user.get("permissions") or []
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]
    return {str(scope).strip() for scope in raw_scopes if str(scope).strip()}


def _require_admin_client_requests_read(current_user: dict) -> None:
    role = str(
        current_user.get("role")
        or current_user.get("user_role")
        or current_user.get("account_role")
        or ""
    ).strip()
    scopes = _admin_client_requests_scopes(current_user)
    allowed_roles = {
        "admin",
        "administrator",
        "owner_admin",
        "ops_admin",
        "billing_admin",
        "support_admin",
        "security_admin",
    }
    allowed_scopes = {
        "*",
        "admin",
        "admin:*",
        "admin:read",
        "admin:clients:read",
        "admin:settings",
    }

    if role in allowed_roles or scopes.intersection(allowed_scopes):
        return

    raise HTTPException(
        status_code=403,
        detail="Admin client request inbox requires admin client read access.",
    )


def _admin_client_request_summary(entry: dict, fallback_user_id: str) -> dict:
    request_id = str(entry.get("request_id") or entry.get("id") or "")
    short_id = str(entry.get("short_id") or request_id[-8:] or "")
    client_id = str(entry.get("client_id") or fallback_user_id)
    request_type = str(entry.get("request_type") or "")
    requested_plan = str(entry.get("requested_plan") or "")
    request_status = str(entry.get("status") or "pending")
    created_at = str(entry.get("created_at") or "")
    source = str(entry.get("source") or "client_settings")

    return {
        "request_id": request_id,
        "short_id": short_id,
        "client_id": client_id,
        "request_type": request_type,
        "requested_plan": requested_plan,
        "status": request_status,
        "created_at": created_at,
        "source": source,
    }


def _admin_client_request_user_id_from_path(path) -> str:
    stem = str(path.stem)
    if stem.startswith("settings_"):
        return stem.replace("settings_", "", 1)
    return stem


def _admin_client_request_raw_files() -> list:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(_DATA_DIR.glob("*.json"))


@router.get("/admin/subscription-analytics", response_model=dict)
async def get_admin_subscription_analytics(
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_read(current_user)
    return build_admin_subscription_analytics(_DATA_DIR)


@router.get("/admin/client-requests", response_model=dict)
async def list_admin_client_requests(
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_read(current_user)

    summaries: list[dict] = []

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)
        for entry in entries:
            if isinstance(entry, dict):
                summaries.append(
                    _admin_client_request_summary(entry, fallback_user_id)
                )

    summaries.sort(
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )
    latest = summaries[:50]

    status_counts: dict[str, int] = {}
    for item in summaries:
        request_status = str(item.get("status") or "pending")
        status_counts[request_status] = status_counts.get(request_status, 0) + 1

    return {
        "status": "ready",
        "request_count": len(summaries),
        "latest_count": len(latest),
        "status_counts": status_counts,
        "latest_requests": latest,
        "message": "Admin client requests inbox is ready.",
    }


_ADMIN_REQUEST_DETAIL_FORBIDDEN_MARKERS = (
    "api_key",
    "encrypted_key",
    "provider_secret",
    "raw key",
    "/settings/llm-provider",
    "/settings/api-keys",
)


def _admin_safe_request_text(value) -> str:
    text = str(value or "")
    lowered = text.lower()
    for marker in _ADMIN_REQUEST_DETAIL_FORBIDDEN_MARKERS:
        if marker in lowered:
            return "[redacted]"
    return text[:2000]


def _admin_client_request_next_action(request_status: str) -> str:
    normalized = str(request_status or "pending").strip().lower()
    if normalized == "pending":
        return "Review request context and decide the next safe admin action."
    if normalized == "reviewed":
        return "Decide whether to approve, reject, or draft a supervisor response."
    if normalized == "approved":
        return "Execute the approved admin-controlled operation, then complete it."
    if normalized == "rejected":
        return "Wait for client clarification or reopen the review if needed."
    if normalized == "completed":
        return "No immediate admin action is required."
    return "Review request state before taking admin action."


def _admin_client_request_timeline(entry: dict) -> list[dict]:
    history = entry.get("status_history") or entry.get("timeline") or entry.get("history") or []
    timeline: list[dict] = []

    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            timeline.append(
                {
                    "status": _admin_safe_request_text(item.get("status") or entry.get("status") or "pending"),
                    "at": _admin_safe_request_text(
                        item.get("at")
                        or item.get("created_at")
                        or item.get("timestamp")
                        or entry.get("created_at")
                        or ""
                    ),
                    "source": _admin_safe_request_text(item.get("source") or entry.get("source") or "client_settings"),
                }
            )

    if timeline:
        return timeline

    return [
        {
            "status": _admin_safe_request_text(entry.get("status") or "pending"),
            "at": _admin_safe_request_text(entry.get("created_at") or ""),
            "source": _admin_safe_request_text(entry.get("source") or "client_settings"),
        }
    ]


def _admin_client_request_detail(entry: dict, fallback_user_id: str) -> dict:
    summary = _admin_client_request_summary(entry, fallback_user_id)
    request_status = str(summary.get("status") or "pending")

    return {
        "request_id": summary["request_id"],
        "short_id": summary["short_id"],
        "client_id": summary["client_id"],
        "user_id": _admin_safe_request_text(entry.get("user_id") or summary["client_id"] or fallback_user_id),
        "role": _admin_safe_request_text(entry.get("role") or "client"),
        "request_type": summary["request_type"],
        "request_label": _admin_safe_request_text(entry.get("request_label") or summary["request_type"]),
        "requested_plan": summary["requested_plan"],
        "approved_plan": _admin_safe_request_text(entry.get("approved_plan") or ""),
        "plan_source": _admin_safe_request_text(entry.get("plan_source") or ""),
        "plan_applied": bool(entry.get("plan_applied")),
        "plan_applied_at": _admin_safe_request_text(entry.get("plan_applied_at") or ""),
        "plan_applied_by": _admin_safe_request_text(entry.get("plan_applied_by") or ""),
        "status": request_status,
        "source": summary["source"],
        "created_at": summary["created_at"],
        "updated_at": _admin_safe_request_text(entry.get("updated_at") or summary["created_at"]),
        "message": _admin_safe_request_text(entry.get("message") or ""),
        "timeline": _admin_client_request_timeline(entry),
        "next_admin_action": _admin_client_request_next_action(request_status),
            "supervisor_response_drafts": _admin_safe_response_drafts(entry),
            "supervisor_responses": _admin_safe_supervisor_responses(entry),
    }


@router.get("/admin/client-requests/{request_id}", response_model=dict)
async def get_admin_client_request_detail(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_read(current_user)

    requested = str(request_id or "").strip()
    if not requested:
        raise HTTPException(status_code=404, detail="Client request not found.")

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            summary = _admin_client_request_summary(entry, fallback_user_id)
            if requested in {summary["request_id"], summary["short_id"]}:
                return {
                    "status": "ready",
                    "request": _admin_client_request_detail(entry, fallback_user_id),
                }

    raise HTTPException(status_code=404, detail="Client request not found.")



_ADMIN_RESPONSE_DRAFT_FORBIDDEN_MARKERS = (
    "api_key",
    "encrypted_key",
    "provider_secret",
    "raw key",
    "/settings/llm-provider",
    "/settings/api-keys",
)


def _admin_response_draft_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _admin_response_draft_actor(current_user: dict) -> str:
    actor = str(
        current_user.get("email")
        or current_user.get("user_id")
        or current_user.get("sub")
        or current_user.get("role")
        or "admin"
    ).strip()
    return actor or "admin"


def _admin_safe_response_draft_text(value) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    for marker in _ADMIN_RESPONSE_DRAFT_FORBIDDEN_MARKERS:
        text = re.sub(re.escape(marker), "[redacted]", text, flags=re.IGNORECASE)
    return text[:4000]


def _admin_generate_supervisor_response_draft(entry: dict) -> str:
    request_type = str(entry.get("request_type") or "").strip().lower()
    requested_plan = str(entry.get("requested_plan") or "").strip()

    if request_type == "enterprise_integration_upgrade":
        plan_text = f" for {requested_plan}" if requested_plan else ""
        return (
            "Thanks for your request. We have reviewed your Enterprise "
            f"Integration upgrade request{plan_text}. The admin team will verify "
            "eligibility and prepare the next safe action. We will not ask you "
            "to paste secrets or credentials in messages."
        )

    if request_type == "provider_setup_help":
        return (
            "Thanks for your provider setup request. Please keep provider "
            "credentials local and use the secure provider setup flow. Do not "
            "paste secrets into support messages. The admin team can help verify "
            "connection status safely."
        )

    if request_type == "billing_usage_review":
        return (
            "Thanks for your billing and usage review request. The admin team "
            "can review usage metadata and quota state without exposing private "
            "credentials."
        )

    return (
        "Thanks for contacting support. We reviewed your request and will "
        "follow up with the next safe action. Please avoid sending secrets or "
        "credentials in messages."
    )


def _admin_safe_response_drafts(entry: dict) -> list[dict]:
    drafts = entry.get("supervisor_response_drafts") or []
    if not isinstance(drafts, list):
        return []

    safe_drafts = []
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        safe_drafts.append(
            {
                "draft_id": str(draft.get("draft_id") or ""),
                "request_id": str(draft.get("request_id") or ""),
                "body": _admin_safe_response_draft_text(draft.get("body")),
                "created_at": str(draft.get("created_at") or ""),
                "updated_at": str(draft.get("updated_at") or ""),
                "source": str(draft.get("source") or "admin_clients_panel"),
                "state": str(draft.get("state") or "draft"),
                "mode": str(draft.get("mode") or "manual"),
                "actor": str(draft.get("actor") or ""),
                "template_id": _admin_safe_response_draft_text(
                    draft.get("template_id")
                ),
                "note": _admin_safe_response_draft_text(draft.get("note")),
            }
        )
    return safe_drafts[-5:]


def _append_admin_response_draft_history(
    entry: dict,
    *,
    at: str,
    actor: str,
    note: str,
) -> None:
    history = entry.get("status_history")
    if not isinstance(history, list):
        history = []

    history.append(
        {
            "status": str(entry.get("status") or "pending"),
            "event": "response_draft_saved",
            "at": at,
            "actor": actor,
            "source": "admin_clients_panel",
            "note": note,
        }
    )
    entry["status_history"] = history



def _admin_supervisor_response_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _admin_supervisor_response_actor(current_user: dict) -> str:
    return _admin_response_draft_actor(current_user)


def _admin_safe_supervisor_response_text(value) -> str:
    return _admin_safe_response_draft_text(value)


def _admin_find_response_draft(entry: dict, draft_id: str) -> dict | None:
    drafts = entry.get("supervisor_response_drafts") or []
    if not isinstance(drafts, list):
        return None

    safe_draft_id = str(draft_id or "").strip()
    if safe_draft_id:
        for draft in drafts:
            if not isinstance(draft, dict):
                continue
            if str(draft.get("draft_id") or "") == safe_draft_id:
                return draft

    for draft in reversed(drafts):
        if isinstance(draft, dict) and draft.get("body"):
            return draft
    return None


def _admin_find_supervisor_response_for_draft(
    entry: dict,
    draft_id: str,
) -> dict | None:
    """Return an already sent supervisor response for a response draft."""
    safe_draft_id = str(draft_id or "").strip()
    if not safe_draft_id:
        return None

    responses = entry.get("supervisor_responses") or []
    if not isinstance(responses, list):
        return None

    for response in reversed(responses):
        if not isinstance(response, dict):
            continue
        if str(response.get("draft_id") or "").strip() == safe_draft_id:
            return response

    return None


def _admin_safe_supervisor_response_record(response: dict) -> dict:
    return {
        "response_id": str(response.get("response_id") or ""),
        "request_id": str(response.get("request_id") or ""),
        "draft_id": str(response.get("draft_id") or ""),
        "body": _admin_safe_supervisor_response_text(response.get("body")),
        "sent_at": str(response.get("sent_at") or ""),
        "source": str(response.get("source") or "admin_clients_panel"),
        "state": str(response.get("state") or "sent"),
        "actor": str(response.get("actor") or ""),
        "event": str(response.get("event") or "supervisor_response_sent"),
    }


def _client_safe_supervisor_responses(entry: dict) -> list[dict]:
    responses = entry.get("supervisor_responses") or []
    if not isinstance(responses, list):
        return []

    safe_responses = []
    for response in responses:
        if isinstance(response, dict):
            safe_responses.append(_admin_safe_supervisor_response_record(response))
    return safe_responses[-5:]


def _admin_safe_supervisor_responses(entry: dict) -> list[dict]:
    return _client_safe_supervisor_responses(entry)


def _append_admin_supervisor_response_history(
    entry: dict,
    *,
    at: str,
    actor: str,
    note: str,
) -> None:
    history = entry.get("status_history")
    if not isinstance(history, list):
        history = []

    history.append(
        {
            "status": str(entry.get("status") or "pending"),
            "event": "supervisor_response_sent",
            "at": at,
            "actor": actor,
            "source": "admin_clients_panel",
            "note": note,
        }
    )
    entry["status_history"] = history


_ADMIN_REQUEST_STATUS_ACTIONS = (
    "pending",
    "reviewed",
    "approved",
    "rejected",
    "completed",
)


def _require_admin_client_requests_write(current_user: dict) -> None:
    _require_admin_client_requests_read(current_user)

    role = str(current_user.get("role") or "").strip().lower()
    session_type = str(current_user.get("session_type") or "").strip().lower()
    scopes = {
        str(scope).strip().lower()
        for scope in current_user.get("scopes") or []
        if scope
    }

    allowed_roles = {
        "admin",
        "owner_admin",
        "security_admin",
        "billing_admin",
        "ops_admin",
    }
    allowed_scopes = {
        "admin:*",
        "admin:clients:write",
        "admin:requests:write",
    }

    if role in allowed_roles or scopes.intersection(allowed_scopes):
        return

    if session_type == "ui_admin":
        return

    raise HTTPException(
        status_code=403,
        detail="Admin client request write access is required.",
    )



def _admin_effective_supervision_user(current_user: dict) -> dict:
    effective = dict(current_user or {})
    if effective.get("supervision_level") or effective.get("supervision_scopes"):
        return effective
    role = str(effective.get("role") or "").strip().lower()
    session_type = str(effective.get("session_type") or "").strip().lower()
    if role == "admin" or session_type in {"ui_admin", "admin"}:
        effective["supervision_level"] = OWNER_SUPERVISOR
    return effective


def _require_admin_supervision_scope(current_user: dict, scope: str) -> None:
    try:
        require_supervision_scope(_admin_effective_supervision_user(current_user), scope)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_admin_client_request_status_supervision_scope(
    current_user: dict,
    next_status: str,
) -> None:
    if str(next_status or "").strip().lower() == "reviewed":
        _require_admin_supervision_scope(current_user, CLIENTS_STATUS_REVIEW_SCOPE)
        return
    _require_admin_supervision_scope(current_user, CLIENTS_STATUS_DECIDE_SCOPE)


def _admin_request_status_now_iso() -> str:
    datetime_module = __import__("datetime")
    return datetime_module.datetime.now(datetime_module.timezone.utc).isoformat()


def _normalize_admin_request_status(value) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _ADMIN_REQUEST_STATUS_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported client request status action.",
        )
    return normalized


def _admin_request_status_note(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""

    note = payload.get("note") or payload.get("admin_note") or ""
    return _admin_safe_request_text(note)[:500]


def _admin_request_status_actor(current_user: dict) -> str:
    return _admin_safe_request_text(
        current_user.get("sub")
        or current_user.get("user_id")
        or current_user.get("client_id")
        or current_user.get("role")
        or "admin"
    )



def _admin_audit_path():
    return _DATA_DIR / "admin_audit.jsonl"


def _admin_audit_actor(current_user: dict) -> str:
    return str(
        current_user.get("email")
        or current_user.get("user_id")
        or current_user.get("sub")
        or "admin"
    )


def _admin_audit_actor_level(current_user: dict) -> str:
    return str(current_user.get("supervision_level") or "owner_supervisor")


def _admin_audit_session_key_id(current_user: dict) -> str | None:
    value = (
        current_user.get("session_key_id")
        or current_user.get("supervisor_session_key_id")
        or current_user.get("supervisor_key_id")
    )
    if value is None:
        return None
    return str(value)


def _admin_audit_request_client_id(
    entry: dict | None,
    summary: dict | None,
    fallback_user_id: str | None,
) -> str | None:
    if isinstance(summary, dict):
        value = summary.get("client_id") or summary.get("user_id")
        if value:
            return str(value)
    if isinstance(entry, dict):
        value = entry.get("client_id") or entry.get("user_id")
        if value:
            return str(value)
    if fallback_user_id:
        return str(fallback_user_id)
    return None


def _record_admin_request_audit_event(
    *,
    current_user: dict,
    action: str,
    target_id: str,
    result: str,
    client_id: str | None = None,
    safe_note: str | None = None,
    reason: str | None = None,
    request_path: str | None = None,
    metadata: dict | None = None,
) -> None:
    append_admin_audit_event(
        audit_path=_admin_audit_path(),
        actor=_admin_audit_actor(current_user),
        actor_level=_admin_audit_actor_level(current_user),
        session_key_id=_admin_audit_session_key_id(current_user),
        action=action,
        target_type="client_request",
        target_id=target_id,
        client_id=client_id,
        source="admin_clients_panel",
        result=result,
        safe_note=safe_note,
        reason=reason,
        request_path=request_path,
        metadata=metadata,
    )


def _append_admin_request_status_history(
    entry: dict,
    *,
    next_status: str,
    at: str,
    actor: str,
    note: str,
) -> None:
    history = entry.get("status_history")
    if not isinstance(history, list):
        history = []

    event = {
        "status": next_status,
        "at": at,
        "source": "admin_clients_panel",
        "actor": actor,
    }
    if note:
        event["note"] = note

    history.append(event)
    entry["status_history"] = history



def _admin_client_request_apply_plan_error_status(
    exc: ClientRequestPlanApplyError,
) -> int:
    reason = str(getattr(exc, "reason", "") or str(exc) or "").strip()
    if reason == "request_not_approved":
        return status.HTTP_409_CONFLICT
    if reason == "unsupported_plan":
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_400_BAD_REQUEST


def _admin_client_request_apply_plan_error_reason(
    exc: ClientRequestPlanApplyError,
) -> str:
    reason = str(getattr(exc, "reason", "") or str(exc) or "").strip()
    return reason or "invalid_request"



DIRECT_ADMIN_PLAN_SOURCE = "settings"


def _supported_admin_direct_plan(plan_value) -> tuple[str, int]:
    try:
        return supported_verified_plan(plan_value)
    except (KeyError, TypeError, ValueError):
        return "", 0


def _admin_direct_plan_payload_value(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("plan_id", "plan", "approved_plan"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _record_admin_client_plan_audit_event(
    *,
    current_user: dict,
    action: str,
    client_id: str,
    result: str,
    safe_note: str | None = None,
    reason: str | None = None,
    request_path: str | None = None,
    metadata: dict | None = None,
) -> None:
    append_admin_audit_event(
        audit_path=_admin_audit_path(),
        actor=_admin_audit_actor(current_user),
        actor_level=_admin_audit_actor_level(current_user),
        action=action,
        target_type="client_plan",
        target_id=client_id,
        client_id=client_id,
        source="admin_clients_panel",
        result=result,
        safe_note=safe_note,
        reason=reason,
        request_path=request_path,
        metadata=metadata,
    )


@router.post("/admin/clients/{client_id}/plan", response_model=dict)
async def set_admin_client_plan(
    client_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_write(current_user)

    requested_client_id = str(client_id or "").strip()
    if not requested_client_id:
        raise HTTPException(status_code=404, detail="Client not found.")

    try:
        _require_admin_supervision_scope(current_user, CLIENTS_STATUS_DECIDE_SCOPE)
    except HTTPException:
        _record_admin_client_plan_audit_event(
            current_user=current_user,
            action="admin_client_plan_set_denied",
            client_id=requested_client_id,
            result="denied",
            reason=f"missing_scope: {CLIENTS_STATUS_DECIDE_SCOPE}",
            request_path=f"/settings/admin/clients/{requested_client_id}/plan",
        )
        raise

    requested_plan = _admin_direct_plan_payload_value(payload)
    plan_id, allowance = _supported_admin_direct_plan(requested_plan)
    if not plan_id or allowance <= 0:
        _record_admin_client_plan_audit_event(
            current_user=current_user,
            action="admin_client_plan_set_failed",
            client_id=requested_client_id,
            result="failure",
            reason="unsupported_plan",
            request_path=f"/settings/admin/clients/{requested_client_id}/plan",
            metadata={"requested_plan": requested_plan},
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unsupported_plan")

    raw = _load_raw(requested_client_id)
    if not isinstance(raw, dict):
        raw = {}

    existing_subscription = raw.get("subscription") if isinstance(raw.get("subscription"), dict) else {}
    already_set = (
        str(raw.get("approved_plan") or "").strip() == plan_id
        and str(raw.get("plan_source") or "").strip() == DIRECT_ADMIN_PLAN_SOURCE
        and bool(raw.get("plan_applied"))
        and str(existing_subscription.get("plan_id") or existing_subscription.get("plan") or "").strip()
        == plan_id
    )

    now = _admin_request_status_now_iso()
    actor = _admin_request_status_actor(current_user)

    if not already_set:
        client = raw.get("client") if isinstance(raw.get("client"), dict) else {}
        client["client_id"] = str(client.get("client_id") or requested_client_id)
        raw["client"] = client

        subscription = dict(existing_subscription)
        subscription["plan_id"] = plan_id
        subscription["plan"] = plan_id
        subscription["status"] = str(subscription.get("status") or "active")
        raw["subscription"] = subscription

        raw["approved_plan"] = plan_id
        raw["plan_source"] = DIRECT_ADMIN_PLAN_SOURCE
        raw["plan_applied"] = True
        raw["plan_applied_at"] = now
        raw["plan_applied_by"] = actor
        raw["updated_at"] = now

        history = raw.get("plan_history") if isinstance(raw.get("plan_history"), list) else []
        history.append(
            {
                "event": "plan_set",
                "plan_id": plan_id,
                "plan_source": DIRECT_ADMIN_PLAN_SOURCE,
                "at": now,
                "actor": actor,
                "source": "admin_clients_panel",
            }
        )
        raw["plan_history"] = history

        _save_raw(requested_client_id, raw)

    status_value = "already_set" if already_set else "plan_set"
    _record_admin_client_plan_audit_event(
        current_user=current_user,
        action="admin_client_plan_set",
        client_id=requested_client_id,
        result="success",
        safe_note=f"Direct admin client plan {status_value}.",
        request_path=f"/settings/admin/clients/{requested_client_id}/plan",
        metadata={
            "status": status_value,
            "plan_id": plan_id,
            "plan_source": DIRECT_ADMIN_PLAN_SOURCE,
            "changed": not already_set,
        },
    )

    return {
        "status": status_value,
        "changed": not already_set,
        "client_id": requested_client_id,
        "plan": {
            "plan_id": plan_id,
            "source": DIRECT_ADMIN_PLAN_SOURCE,
            "monthly_unit_allowance": allowance,
        },
        "settings": {
            "approved_plan": plan_id,
            "plan_source": DIRECT_ADMIN_PLAN_SOURCE,
            "plan_applied": True,
            "plan_applied_at": str(raw.get("plan_applied_at") or ""),
            "plan_applied_by": str(raw.get("plan_applied_by") or ""),
        },
    }


@router.post("/admin/client-requests/{request_id}/apply-plan", response_model=dict)
async def apply_admin_client_request_plan(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_write(current_user)

    requested = str(request_id or "").strip()
    try:
        _require_admin_supervision_scope(current_user, CLIENTS_STATUS_DECIDE_SCOPE)
    except HTTPException:
        _record_admin_request_audit_event(
            current_user=current_user,
            action="admin_client_request_plan_apply_denied",
            target_id=requested,
            result="denied",
            reason=f"missing_scope: {CLIENTS_STATUS_DECIDE_SCOPE}",
            request_path=f"/settings/admin/client-requests/{requested}/apply-plan",
        )
        raise

    if not requested:
        raise HTTPException(status_code=404, detail="Client request not found.")

    now = _admin_request_status_now_iso()
    actor = _admin_request_status_actor(current_user)

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            summary = _admin_client_request_summary(entry, fallback_user_id)
            if requested not in {summary["request_id"], summary["short_id"]}:
                continue

            try:
                result = apply_verified_client_request_plan(entry, actor=actor, now=now)
            except ClientRequestPlanApplyError as exc:
                reason = _admin_client_request_apply_plan_error_reason(exc)
                _record_admin_request_audit_event(
                    current_user=current_user,
                    action="admin_client_request_plan_apply_failed",
                    target_id=summary["request_id"],
                    client_id=_admin_audit_request_client_id(
                        entry,
                        summary,
                        fallback_user_id,
                    ),
                    result="failure",
                    reason=reason,
                    request_path=(
                        f"/settings/admin/client-requests/"
                        f"{summary['request_id']}/apply-plan"
                    ),
                    metadata={"reason": reason},
                )
                raise HTTPException(
                    status_code=_admin_client_request_apply_plan_error_status(exc),
                    detail=reason,
                ) from exc

            changed = bool(result.get("changed"))
            if changed:
                path.write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

            plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
            status_value = str(
                result.get("status")
                or ("plan_applied" if changed else "already_applied")
            )
            audit_action = (
                "admin_client_request_plan_applied"
                if changed
                else "admin_client_request_plan_already_applied"
            )
            _record_admin_request_audit_event(
                current_user=current_user,
                action=audit_action,
                target_id=summary["request_id"],
                client_id=_admin_audit_request_client_id(
                    entry,
                    summary,
                    fallback_user_id,
                ),
                result="success",
                safe_note=f"Verified requested plan {status_value}.",
                request_path=(
                    f"/settings/admin/client-requests/"
                    f"{summary['request_id']}/apply-plan"
                ),
                metadata={
                    "status": status_value,
                    "plan_id": plan.get("plan_id"),
                    "plan_source": plan.get("source"),
                    "changed": changed,
                },
            )

            return {
                "status": status_value,
                "plan": plan,
                "changed": changed,
                "request": _admin_client_request_detail(entry, fallback_user_id),
            }

    raise HTTPException(status_code=404, detail="Client request not found.")


@router.post("/admin/client-requests/{request_id}/status", response_model=dict)
async def update_admin_client_request_status(
    request_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_write(current_user)

    requested = str(request_id or "").strip()
    if not requested:
        raise HTTPException(status_code=404, detail="Client request not found.")

    next_status = _normalize_admin_request_status(payload.get("status"))
    required_scope = (
        CLIENTS_STATUS_REVIEW_SCOPE
        if next_status == "reviewed"
        else CLIENTS_STATUS_DECIDE_SCOPE
    )
    try:
        _require_admin_client_request_status_supervision_scope(current_user, next_status)
    except HTTPException:
        _record_admin_request_audit_event(
            current_user=current_user,
            action="admin_client_request_status_denied",
            target_id=requested,
            result="denied",
            reason=f"missing_scope: {required_scope}",
            request_path=f"/settings/admin/client-requests/{requested}/status",
        )
        raise
    now = _admin_request_status_now_iso()
    note = _admin_request_status_note(payload)
    actor = _admin_request_status_actor(current_user)

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            summary = _admin_client_request_summary(entry, fallback_user_id)
            if requested not in {summary["request_id"], summary["short_id"]}:
                continue

            entry["status"] = next_status
            entry["updated_at"] = now
            _append_admin_request_status_history(
                entry,
                next_status=next_status,
                at=now,
                actor=actor,
                note=note,
            )

            path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            _record_admin_request_audit_event(
                current_user=current_user,
                action="admin_client_request_status_updated",
                target_id=summary["request_id"],
                client_id=_admin_audit_request_client_id(
                    entry,
                    summary,
                    fallback_user_id,
                ),
                result="success",
                safe_note=f"Client request status updated to {next_status}.",
                request_path=(
                    f"/settings/admin/client-requests/{summary['request_id']}/status"
                ),
                metadata={"status": next_status},
            )

            return {
                "status": "updated",
                "request": _admin_client_request_detail(entry, fallback_user_id),
            }

    raise HTTPException(status_code=404, detail="Client request not found.")

@router.post("/admin/client-requests/{request_id}/response-draft", response_model=dict)
async def save_admin_client_request_response_draft(
    request_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_write(current_user)

    requested = str(request_id or "").strip()
    try:
        _require_admin_supervision_scope(current_user, CLIENTS_DRAFT_SCOPE)
    except HTTPException:
        _record_admin_request_audit_event(
            current_user=current_user,
            action="supervisor_response_draft_denied",
            target_id=requested,
            result="denied",
            reason=f"missing_scope: {CLIENTS_DRAFT_SCOPE}",
            request_path=(
                f"/settings/admin/client-requests/{requested}/response-draft"
            ),
        )
        raise

    if not requested:
        raise HTTPException(status_code=404, detail="Client request not found.")

    mode = str(payload.get("mode") or "manual").strip().lower()
    if mode not in {"generate", "manual"}:
        mode = "manual"

    now = _admin_response_draft_now_iso()
    actor = _admin_response_draft_actor(current_user)

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            summary = _admin_client_request_summary(entry, fallback_user_id)
            if requested not in {summary["request_id"], summary["short_id"]}:
                continue

            if mode == "generate":
                body = _admin_generate_supervisor_response_draft(entry)
            else:
                body = _admin_safe_response_draft_text(
                    payload.get("draft") or payload.get("body") or ""
                )

            body = _admin_safe_response_draft_text(body)
            if not body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Draft body is required.",
                )

            drafts = entry.get("supervisor_response_drafts")
            if not isinstance(drafts, list):
                drafts = []

            draft = {
                "draft_id": f"rdraft_{secrets.token_hex(8)}",
                "request_id": summary["request_id"],
                "body": body,
                "created_at": now,
                "updated_at": now,
                "source": "admin_clients_panel",
                "state": "draft",
                "mode": mode,
                "actor": actor,
                "template_id": _admin_safe_response_draft_text(
                    payload.get("template_id")
                ),
                "note": _admin_safe_response_draft_text(payload.get("note")),
            }

            drafts.append(draft)
            entry["supervisor_response_drafts"] = drafts
            entry["updated_at"] = now
            _append_admin_response_draft_history(
                entry,
                at=now,
                actor=actor,
                note="Supervisor response draft saved.",
            )

            path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            safe_draft = _admin_safe_response_drafts(entry)[-1]
            _record_admin_request_audit_event(
                current_user=current_user,
                action="supervisor_response_draft_saved",
                target_id=summary["request_id"],
                client_id=_admin_audit_request_client_id(
                    entry,
                    summary,
                    fallback_user_id,
                ),
                result="success",
                safe_note="Supervisor response draft saved.",
                request_path=(
                    f"/settings/admin/client-requests/"
                    f"{summary['request_id']}/response-draft"
                ),
                metadata={
                    "draft_id": safe_draft.get("draft_id"),
                    "mode": mode,
                    "template_id": safe_draft.get("template_id"),
                },
            )
            return {
                "status": "draft_saved",
                "request": _admin_client_request_detail(entry, fallback_user_id),
                "draft": safe_draft,
            }

    raise HTTPException(status_code=404, detail="Client request not found.")



@router.post("/admin/client-requests/{request_id}/supervisor-response", response_model=dict)
async def send_admin_client_request_supervisor_response(
    request_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_client_requests_write(current_user)

    requested = str(request_id or "").strip()
    try:
        _require_admin_supervision_scope(current_user, CLIENTS_RESPOND_SCOPE)
    except HTTPException:
        _record_admin_request_audit_event(
            current_user=current_user,
            action="supervisor_response_denied",
            target_id=requested,
            result="denied",
            reason=f"missing_scope: {CLIENTS_RESPOND_SCOPE}",
            request_path=(
                f"/settings/admin/client-requests/{requested}/supervisor-response"
            ),
        )
        raise

    if not requested:
        raise HTTPException(status_code=404, detail="Client request not found.")

    now = _admin_supervisor_response_now_iso()
    actor = _admin_supervisor_response_actor(current_user)
    draft_id = _admin_safe_supervisor_response_text(payload.get("draft_id"))
    body = _admin_safe_supervisor_response_text(
        payload.get("body") or payload.get("draft") or ""
    )

    for path in _admin_client_request_raw_files():
        if not path.is_file():
            continue

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue

        entries = raw.get("client_requests") or []
        if not isinstance(entries, list):
            continue

        fallback_user_id = _admin_client_request_user_id_from_path(path)

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            summary = _admin_client_request_summary(entry, fallback_user_id)
            if requested not in {summary["request_id"], summary["short_id"]}:
                continue

            draft = _admin_find_response_draft(entry, draft_id)
            if not body and draft:
                body = _admin_safe_supervisor_response_text(draft.get("body"))

            existing_response = _admin_find_supervisor_response_for_draft(
                entry,
                draft_id,
            )
            if existing_response is not None:
                safe_response = _admin_safe_supervisor_response_record(existing_response)
                _record_admin_request_audit_event(
                    current_user=current_user,
                    action="supervisor_response_already_sent",
                    target_id=summary["request_id"],
                    client_id=_admin_audit_request_client_id(
                        entry,
                        summary,
                        fallback_user_id,
                    ),
                    result="already_sent",
                    safe_note="Supervisor response already sent for this draft.",
                    request_path=(
                        f"/settings/admin/client-requests/"
                        f"{summary['request_id']}/supervisor-response"
                    ),
                    metadata={
                        "draft_id": draft_id,
                        "response_id": safe_response.get("response_id"),
                    },
                )
                return {
                    "ok": True,
                    "status": "already_sent",
                    "message": "Supervisor response already sent for this draft.",
                    "request": _admin_client_request_detail(entry, fallback_user_id),
                    "response": safe_response,
                }

            if not body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Supervisor response body is required.",
                )

            responses = entry.get("supervisor_responses")
            if not isinstance(responses, list):
                responses = []

            response = {
                "response_id": f"sresp_{secrets.token_hex(8)}",
                "request_id": summary["request_id"],
                "draft_id": str(draft.get("draft_id") or "") if draft else draft_id,
                "body": body,
                "sent_at": now,
                "source": "admin_clients_panel",
                "state": "sent",
                "actor": actor,
                "event": "supervisor_response_sent",
            }

            responses.append(response)
            entry["supervisor_responses"] = responses
            entry["updated_at"] = now

            if draft:
                draft["state"] = "sent"
                draft["sent_at"] = now
                draft["updated_at"] = now

            _append_admin_supervisor_response_history(
                entry,
                at=now,
                actor=actor,
                note="Supervisor response sent to client timeline.",
            )

            path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            safe_response = _admin_safe_supervisor_response_record(response)
            _record_admin_request_audit_event(
                current_user=current_user,
                action="supervisor_response_sent",
                target_id=summary["request_id"],
                client_id=_admin_audit_request_client_id(
                    entry,
                    summary,
                    fallback_user_id,
                ),
                result="success",
                safe_note="Supervisor response sent to client timeline.",
                request_path=(
                    f"/settings/admin/client-requests/"
                    f"{summary['request_id']}/supervisor-response"
                ),
                metadata={
                    "draft_id": response.get("draft_id"),
                    "response_id": safe_response.get("response_id"),
                },
            )
            return {
                "status": "sent",
                "message": "Supervisor response sent to client timeline.",
                "supervisor_response": safe_response,
                "request": _admin_client_request_detail(entry, fallback_user_id),
            }

    raise HTTPException(status_code=404, detail="Client request not found.")


@router.post("/client-request", response_model=dict)
async def submit_client_request(
    body: ClientRequestPayload,
    current_user: dict = Depends(get_current_user),
):
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    client_id = str(current_user.get("client_id") or user_id)
    message = body.message.strip()
    if len(message) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request message must be at least 10 characters.",
        )

    request_type = _normalize_client_request_type(body.request_type)
    requested_plan = (
        body.requested_plan.strip()
        if body.requested_plan
        else ""
    )
    now = datetime.now(UTC).isoformat()

    raw = _load_raw(user_id)
    requests = _client_requests(raw)
    entry = {
        "id": f"creq_{secrets.token_hex(8)}",
        "status": "pending",
        "source": "client_settings",
        "created_at": now,
        "updated_at": now,
        "user_id": user_id,
        "client_id": client_id,
        "role": current_user.get("role", "client"),
        "request_type": request_type,
        "request_label": CLIENT_REQUEST_TYPE_LABELS[request_type],
        "requested_plan": requested_plan,
        "message": message,
    }

    requests.append(entry)
    raw["client_requests"] = requests[-100:]
    _save_raw(user_id, raw)

    return {
        "status": "submitted",
        "request": _client_request_summary(entry),
        "request_count": len(raw["client_requests"]),
        "message": "Client request submitted for admin follow-up.",
    }


def _client_provider_connection_payload(raw: dict[str, Any]) -> dict[str, Any]:
    merged = _merge_defaults(raw)
    provider_status = merged.get("llm_provider", {})
    configured = bool(provider_status.get("configured"))

    return {
        "configured": configured,
        "status": "configured" if configured else "not_configured",
        "provider": provider_status.get("provider") or "",
        "model": provider_status.get("model") or "",
        "last_tested": provider_status.get("last_tested"),
        "secret_status": "stored_encrypted" if provider_status.get("encrypted_key") else "not_stored",
        "available_providers": sorted(provider_ids()),
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "message": (
            "Client BYOK provider connection is configured."
            if configured
            else "Client BYOK provider connection is not configured yet."
        ),
    }


@router.get("/provider-connection", response_model=dict)
async def get_provider_connection(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    return _client_provider_connection_payload(raw)


@router.put("/provider-connection/setup", response_model=dict)
async def save_client_provider_connection(
    body: ClientProviderConnectionSetupPayload,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub", "default")
    provider = _normalize_client_provider(body.provider)
    provider_secret = str(body.provider_secret or "").strip()
    model = str(body.model or "").strip()

    if not provider_secret and provider not in CLIENT_PROVIDER_SECRET_OPTIONAL_PROVIDERS:
        raise HTTPException(status_code=400, detail="Provider secret is required")

    encrypted = _encrypt_api_key(provider_secret, user_id) if provider_secret else None
    if provider_secret and not encrypted:
        raise HTTPException(status_code=503, detail="Provider secret encryption is unavailable")

    raw = _load_raw(user_id)
    previous = raw.get("llm_provider", {})
    raw["llm_provider"] = {
        "configured": bool(provider and (encrypted or provider in CLIENT_PROVIDER_SECRET_OPTIONAL_PROVIDERS)),
        "provider": provider,
        "model": model,
        "last_tested": previous.get("last_tested"),
    }
    if encrypted:
        raw["llm_provider"]["encrypted_key"] = encrypted

    _save_raw(user_id, raw)
    payload = _client_provider_connection_payload(raw)
    payload["status"] = "saved"
    payload["message"] = "Client BYOK provider connection saved. Raw provider secrets are never returned."
    return payload


@router.delete("/provider-connection/setup", response_model=dict)
async def clear_client_provider_connection(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub", "default")
    raw = _load_raw(user_id)
    raw["llm_provider"] = {"configured": False, "provider": "", "model": ""}
    _save_raw(user_id, raw)
    payload = _client_provider_connection_payload(raw)
    payload["status"] = "cleared"
    payload["message"] = "Client BYOK provider connection cleared."
    return payload


@router.post("/provider-connection/test", response_model=TestConnectionResult)
async def test_client_provider_connection(
    body: ClientProviderConnectionSetupPayload,
    current_user: dict = Depends(get_current_user),
):
    provider = _normalize_client_provider(body.provider)
    config = LLMProviderConfig(
        provider=provider,
        api_key=str(body.provider_secret or "").strip(),
        model=str(body.model or "").strip(),
    )
    return await test_llm_provider(config, current_user)

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


def _client_api_key_integration_eligible_plans() -> list[str]:
    return sorted({
        *ENTERPRISE_INTEGRATION_PLANS,
        "enterprise_private",
    })


def _allows_client_api_key_integration(plan_id: str | None) -> bool:
    normalized = normalize_plan_id(plan_id)
    return allows_enterprise_integration(normalized) or normalized == "enterprise_private"


def _resolve_client_api_key_integration_plan_id(
    user_id: str,
    raw: dict[str, Any],
    current_user: dict[str, Any],
) -> str:
    candidates: list[Any] = [
        current_user.get("plan_id"),
        current_user.get("plan"),
    ]

    billing_subs = _load_billing_subscriptions()
    user_subs = [sub for sub in billing_subs if sub.get("user_id") == user_id]
    if user_subs:
        latest = max(user_subs, key=lambda sub: sub.get("created_at", ""))
        candidates.extend([
            latest.get("plan_id"),
            latest.get("plan"),
        ])

    subscription = raw.get("subscription", {})
    if isinstance(subscription, dict):
        candidates.extend([
            subscription.get("plan_id"),
            subscription.get("plan"),
        ])

    for candidate in candidates:
        normalized = normalize_plan_id(str(candidate) if candidate is not None else None)
        if normalized:
            return normalized

    return "starter"


def _active_client_integration_keys(
    raw: dict[str, Any],
    client_id: str,
) -> list[dict[str, Any]]:
    raw_keys = raw.get("api_keys", [])
    if isinstance(raw_keys, dict):
        keys = list(raw_keys.values())
    elif isinstance(raw_keys, list):
        keys = raw_keys
    else:
        keys = []

    visible_keys: list[dict[str, Any]] = []
    for key in keys:
        if not isinstance(key, dict):
            continue

        if key.get("status") in {"revoked", "disabled", "expired"}:
            continue
        if key.get("revoked_at"):
            continue

        key_client_id = str(key.get("client_id") or key.get("user_id") or "")
        if client_id and key_client_id and key_client_id != client_id:
            continue

        quota_limit = key.get("quota_limit")
        quota_used = int(key.get("quota_used", 0) or 0)
        quota_remaining = (
            max(int(quota_limit) - quota_used, 0)
            if isinstance(quota_limit, int) and quota_limit >= 0
            else None
        )

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
            "client_id": key.get("client_id"),
            "scopes": key.get("scopes", []),
            "created_at": key.get("created_at", ""),
            "last_used_at": key.get("last_used_at"),
            "usage_count": key.get("usage_count", 0),
            "plan_id": key.get("plan_id"),
            "quota_scope": key.get("quota_scope"),
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "quota_rejected_count": key.get("quota_rejected_count", 0),
            "expires_at": key.get("expires_at"),
        })

    return visible_keys


@router.get("/api-key-integration", response_model=dict)
async def get_api_key_integration(current_user: dict = Depends(get_current_user)):
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    client_id = str(current_user.get("client_id") or user_id)
    raw = _load_raw(user_id)

    plan_id = _resolve_client_api_key_integration_plan_id(
        user_id,
        raw,
        current_user,
    )
    eligible_plans = _client_api_key_integration_eligible_plans()
    enabled = _allows_client_api_key_integration(plan_id)

    if not enabled:
        return {
            "enabled": False,
            "status": "locked",
            "plan_id": plan_id,
            "eligible_plans": eligible_plans,
            "message": (
                "API Key Integration is available for Enterprise "
                "Integration plans."
            ),
            "keys": [],
            "key_count": 0,
        }

    keys = _active_client_integration_keys(raw, client_id)

    return {
        "enabled": True,
        "status": "available",
        "plan_id": plan_id,
        "eligible_plans": eligible_plans,
        "message": "API Key Integration is available for this client.",
        "keys": keys,
        "key_count": len(keys),
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


@router.get("/usage-summary", response_model=dict)
async def get_usage_summary(current_user: dict = Depends(get_current_user)):
    """Return the current client usage summary from the Maestro ledger.

    Backend/API only. This endpoint intentionally does not alter console UI,
    layout, CSS, JavaScript, or navigation.
    """

    client_id = str(
        current_user.get("client_id")
        or current_user.get("user_id")
        or current_user.get("sub")
        or ""
    )
    api_key_id = str(current_user.get("api_key_id") or "")
    api_key_filter = api_key_id if api_key_id and api_key_id != "env" else None

    return summarize_usage_logs(
        client_id=client_id,
        api_key_id=api_key_filter,
        latest_limit=10,
    )



@router.get("/client/usage-summary", response_model=dict)
async def get_client_usage_summary(current_user: dict = Depends(get_current_user)):
    """Return a client-scoped usage/subscription summary.

    This endpoint intentionally ignores query parameters such as client_id and
    derives the identity only from the authenticated current_user.
    """

    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    client_id = str(current_user.get("client_id") or user_id)
    api_key_id = str(current_user.get("api_key_id") or "")
    api_key_filter = api_key_id if api_key_id and api_key_id != "env" else None

    raw = _load_raw(user_id)
    ledger_summary = summarize_usage_logs(
        client_id=client_id,
        api_key_id=api_key_filter,
        latest_limit=10,
    )

    return build_client_usage_summary(
        user_id=user_id,
        client_id=client_id,
        ledger_summary=ledger_summary,
        raw_settings=raw,
    )


class SupervisorSessionKeyIssueRequest(BaseModel):
    level: str = Field(..., min_length=1)
    issued_to: str = Field(..., min_length=1)
    session_label: str = ""
    reason: str = ""
    expires_at: str = ""


class SupervisorSessionKeyRevokeRequest(BaseModel):
    reason: str = ""


def _supervisor_session_key_store_path() -> Path:
    return _DATA_DIR / "supervisor_session_keys.json"


def _supervisor_session_key_actor(current_user: dict[str, Any]) -> dict[str, Any]:
    actor = str(
        current_user.get("email")
        or current_user.get("sub")
        or current_user.get("user_id")
        or "admin"
    )
    return {
        **current_user,
        "email": actor,
        "supervision_level": current_user.get("supervision_level")
        or OWNER_SUPERVISOR,
    }


def _audit_supervisor_session_key_event(
    *,
    current_user: dict[str, Any],
    action: str,
    session_key_id: str,
    result: str,
    reason: str = "",
) -> None:
    append_admin_audit_event(
        audit_path=_admin_audit_path(),
        actor=str(
            current_user.get("email")
            or current_user.get("sub")
            or current_user.get("user_id")
            or "admin"
        ),
        actor_level=str(current_user.get("supervision_level") or OWNER_SUPERVISOR),
        action=action,
        target_type="supervisor_session_key",
        target_id=session_key_id,
        source="admin_api_keys_panel",
        result=result,
        reason=reason,
    )


def _require_admin_audit_read(current_user: dict) -> None:
    role = str(
        current_user.get("role")
        or current_user.get("user_role")
        or current_user.get("account_role")
        or ""
    ).strip()
    raw_scopes = current_user.get("scopes") or current_user.get("permissions") or []
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]
    scopes = {str(scope).strip() for scope in raw_scopes if str(scope).strip()}

    allowed_roles = {
        "admin",
        "administrator",
        "owner_admin",
        "ops_admin",
        "security_admin",
    }
    allowed_scopes = {
        "*",
        "admin",
        "admin:*",
        "admin:read",
        "admin:audit:read",
        "admin:settings",
    }

    if role in allowed_roles or scopes.intersection(allowed_scopes):
        return

    raise HTTPException(
        status_code=403,
        detail="Admin audit events require admin audit read access.",
    )


def _safe_admin_audit_limit(limit: int | None) -> int:
    if limit is None:
        return 50
    return max(1, min(int(limit), 100))


@router.get("/admin/audit-events", response_model=dict)
async def list_admin_audit_events(
    limit: int | None = 50,
    current_user: dict = Depends(get_current_user),
):
    _require_admin_audit_read(current_user)
    safe_limit = _safe_admin_audit_limit(limit)
    events = read_admin_audit_events(_admin_audit_path(), limit=safe_limit)
    events.reverse()
    return {
        "status": "ready",
        "audit_events": events,
        "latest_count": len(events),
        "limit": safe_limit,
        "message": "Recent admin audit events are ready.",
    }



@router.post("/admin/supervisor-session-keys", response_model=dict, status_code=201)
async def create_admin_supervisor_session_key(
    payload: SupervisorSessionKeyIssueRequest,
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):
    issuer = _supervisor_session_key_actor(current_user)
    try:
        issued = issue_supervisor_session_key(
            _supervisor_session_key_store_path(),
            issuer,
            {
                "level": payload.level,
                "issued_to": payload.issued_to,
                "session_label": payload.session_label,
                "reason": payload.reason,
                "expires_at": payload.expires_at,
            },
        )
    except PermissionError as exc:
        _audit_supervisor_session_key_event(
            current_user=current_user,
            action="supervisor_session_key_issue_denied",
            session_key_id="unknown",
            result="denied",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor session key issue denied.",
        ) from exc

    record = issued["record"]
    _audit_supervisor_session_key_event(
        current_user=current_user,
        action="supervisor_session_key_issued",
        session_key_id=str(record.get("session_key_id") or "unknown"),
        result="success",
        reason=payload.reason,
    )
    return {"status": "issued", "raw_key": issued["raw_key"], "record": record}


@router.get("/admin/supervisor-session-keys", response_model=dict)
async def list_admin_supervisor_session_keys(
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):
    actor = _supervisor_session_key_actor(current_user)
    keys = list_supervisor_session_keys(_supervisor_session_key_store_path(), actor)
    return {"count": len(keys), "supervisor_session_keys": keys}


@router.post(
    "/admin/supervisor-session-keys/{session_key_id}/revoke",
    response_model=dict,
)
async def revoke_admin_supervisor_session_key(
    session_key_id: str,
    payload: SupervisorSessionKeyRevokeRequest,
    current_user: dict = Depends(require_scope(ADMIN_SETTINGS_SCOPE)),
):
    actor = _supervisor_session_key_actor(current_user)
    try:
        record = revoke_supervisor_session_key(
            _supervisor_session_key_store_path(),
            actor,
            session_key_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor session key not found.",
        ) from exc
    except PermissionError as exc:
        _audit_supervisor_session_key_event(
            current_user=current_user,
            action="supervisor_session_key_revoke_denied",
            session_key_id=session_key_id,
            result="denied",
            reason=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor session key revoke denied.",
        ) from exc

    _audit_supervisor_session_key_event(
        current_user=current_user,
        action="supervisor_session_key_revoked",
        session_key_id=session_key_id,
        result="success",
        reason=payload.reason,
    )
    return {"status": "revoked", "record": record}
