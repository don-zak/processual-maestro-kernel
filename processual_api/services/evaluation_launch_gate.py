"""One-time, supervisor-issued launch gate for the External Evaluation workspace.

This gate controls access to the customer-facing workspace only. It does not
replace, weaken, or extend Evaluation API-key execution authority.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from processual_api.cache.redis import get_redis
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    load_evaluation_authority_state,
)
from processual_api.services.evaluation_grants import (
    EVALUATION_GRANT_ACTIVE,
    find_evaluation_grant,
    refresh_evaluation_grant_status,
)
from processual_api.settings import settings

EVALUATION_LAUNCH_TICKET_TTL_SECONDS = 30 * 60
EVALUATION_WORKSPACE_SESSION_TTL_SECONDS = 2 * 60 * 60
EVALUATION_LAUNCH_COOKIE = "pm_eval_launch_session"
EVALUATION_LAUNCH_QUERY_PARAM = "launch"
_REDIS_PREFIX = "evaluation:workspace-launch:v1:"
_TOKEN_VERSION = 1


class EvaluationLaunchGateError(ValueError):
    """Workspace launch authority is invalid, expired, unavailable, or replayed."""


@dataclass(frozen=True)
class EvaluationLaunchSession:
    owner_user_id: str
    grant_id: str
    issued_at: int
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid") from exc


def _signing_key() -> bytes:
    root = str(settings.jwt_secret or "").encode("utf-8")
    if not root or root == b"CHANGE_ME_IN_PRODUCTION":
        raise EvaluationLaunchGateError("evaluation_launch_signing_key_unavailable")
    return hmac.new(root, b"processual-maestro:external-evaluation-launch:v1", hashlib.sha256).digest()


def _encode(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _b64encode(body)
    signature = hmac.new(_signing_key(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def _decode(token: str, *, expected_kind: str, now: int | None = None) -> dict[str, Any]:
    text = str(token or "").strip()
    try:
        encoded, supplied_signature = text.split(".", 1)
    except ValueError as exc:
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid") from exc
    expected_signature = hmac.new(
        _signing_key(), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(_b64decode(supplied_signature), expected_signature):
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid")
    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except Exception as exc:
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid") from exc
    if not isinstance(payload, dict):
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid")
    if int(payload.get("v", 0) or 0) != _TOKEN_VERSION:
        raise EvaluationLaunchGateError("evaluation_launch_token_version_invalid")
    if str(payload.get("kind") or "") != expected_kind:
        raise EvaluationLaunchGateError("evaluation_launch_token_kind_invalid")
    current = int(time.time() if now is None else now)
    expires_at = int(payload.get("exp", 0) or 0)
    issued_at = int(payload.get("iat", 0) or 0)
    if issued_at <= 0 or expires_at <= current or expires_at <= issued_at:
        raise EvaluationLaunchGateError("evaluation_launch_token_expired")
    return payload


def _ticket_redis_key(ticket_id: str) -> str:
    return f"{_REDIS_PREFIX}{ticket_id}"


async def _require_active_grant(owner_user_id: str, grant_id: str) -> dict[str, Any]:
    try:
        raw = await load_evaluation_authority_state(owner_user_id)
    except EvaluationAuthorityError as exc:
        raise EvaluationLaunchGateError("evaluation_launch_authority_unavailable") from exc
    grant = find_evaluation_grant(raw, grant_id)
    if grant is None:
        raise EvaluationLaunchGateError("evaluation_launch_grant_not_found")
    if refresh_evaluation_grant_status(grant) != EVALUATION_GRANT_ACTIVE:
        raise EvaluationLaunchGateError("evaluation_launch_grant_inactive")
    if bool(grant.get("production_allowed")):
        raise EvaluationLaunchGateError("evaluation_launch_grant_unsafe")
    if str(grant.get("entitlement_source") or "") != "admin_evaluation_grant":
        raise EvaluationLaunchGateError("evaluation_launch_grant_authority_invalid")
    return grant


async def issue_evaluation_launch_ticket(
    *,
    owner_user_id: str,
    grant_id: str,
    now: int | None = None,
) -> dict[str, Any]:
    """Issue a one-time launch ticket after supervisor/admin authority succeeds."""

    owner = str(owner_user_id or "").strip()
    grant = str(grant_id or "").strip()
    if not owner or not grant:
        raise EvaluationLaunchGateError("evaluation_launch_subject_required")
    await _require_active_grant(owner, grant)

    redis = await get_redis()
    if redis is None:
        raise EvaluationLaunchGateError("evaluation_launch_replay_store_unavailable")

    current = int(time.time() if now is None else now)
    ticket_id = secrets.token_urlsafe(24)
    expires_at = current + EVALUATION_LAUNCH_TICKET_TTL_SECONDS
    record = json.dumps(
        {"owner_user_id": owner, "grant_id": grant, "exp": expires_at},
        separators=(",", ":"),
        sort_keys=True,
    )
    stored = await redis.set(
        _ticket_redis_key(ticket_id),
        record,
        ex=EVALUATION_LAUNCH_TICKET_TTL_SECONDS,
        nx=True,
    )
    if not stored:
        raise EvaluationLaunchGateError("evaluation_launch_ticket_store_failed")

    token = _encode(
        {
            "v": _TOKEN_VERSION,
            "kind": "launch_ticket",
            "jti": ticket_id,
            "owner_user_id": owner,
            "grant_id": grant,
            "iat": current,
            "exp": expires_at,
        }
    )
    return {
        "launch_ticket": token,
        "expires_in_seconds": EVALUATION_LAUNCH_TICKET_TTL_SECONDS,
        "workspace_session_seconds": EVALUATION_WORKSPACE_SESSION_TTL_SECONDS,
        "one_time": True,
        "production_allowed": False,
        "execution_authority_replaced": False,
    }


async def redeem_evaluation_launch_ticket(
    token: str,
    *,
    now: int | None = None,
) -> tuple[str, EvaluationLaunchSession]:
    """Consume exactly one ticket and mint the longer workspace session cookie."""

    payload = _decode(token, expected_kind="launch_ticket", now=now)
    ticket_id = str(payload.get("jti") or "").strip()
    owner = str(payload.get("owner_user_id") or "").strip()
    grant = str(payload.get("grant_id") or "").strip()
    if not ticket_id or not owner or not grant:
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid")

    redis = await get_redis()
    if redis is None:
        raise EvaluationLaunchGateError("evaluation_launch_replay_store_unavailable")
    key = _ticket_redis_key(ticket_id)
    try:
        record = await redis.getdel(key)
    except AttributeError:
        transaction = redis.pipeline(transaction=True)
        await transaction.get(key)
        await transaction.delete(key)
        values = await transaction.execute()
        record = values[0] if values else None
    if not record:
        raise EvaluationLaunchGateError("evaluation_launch_ticket_consumed_or_expired")
    try:
        stored = json.loads(record)
    except Exception as exc:
        raise EvaluationLaunchGateError("evaluation_launch_ticket_record_invalid") from exc
    if (
        str(stored.get("owner_user_id") or "") != owner
        or str(stored.get("grant_id") or "") != grant
    ):
        raise EvaluationLaunchGateError("evaluation_launch_ticket_subject_mismatch")

    await _require_active_grant(owner, grant)
    current = int(time.time() if now is None else now)
    expires_at = current + EVALUATION_WORKSPACE_SESSION_TTL_SECONDS
    session_token = _encode(
        {
            "v": _TOKEN_VERSION,
            "kind": "workspace_session",
            "owner_user_id": owner,
            "grant_id": grant,
            "iat": current,
            "exp": expires_at,
        }
    )
    return session_token, EvaluationLaunchSession(
        owner_user_id=owner,
        grant_id=grant,
        issued_at=current,
        expires_at=expires_at,
    )


async def validate_evaluation_workspace_session(
    token: str,
    *,
    now: int | None = None,
) -> EvaluationLaunchSession:
    payload = _decode(token, expected_kind="workspace_session", now=now)
    owner = str(payload.get("owner_user_id") or "").strip()
    grant = str(payload.get("grant_id") or "").strip()
    if not owner or not grant:
        raise EvaluationLaunchGateError("evaluation_launch_token_invalid")
    await _require_active_grant(owner, grant)
    return EvaluationLaunchSession(
        owner_user_id=owner,
        grant_id=grant,
        issued_at=int(payload["iat"]),
        expires_at=int(payload["exp"]),
    )


__all__ = [
    "EVALUATION_LAUNCH_COOKIE",
    "EVALUATION_LAUNCH_QUERY_PARAM",
    "EVALUATION_LAUNCH_TICKET_TTL_SECONDS",
    "EVALUATION_WORKSPACE_SESSION_TTL_SECONDS",
    "EvaluationLaunchGateError",
    "EvaluationLaunchSession",
    "issue_evaluation_launch_ticket",
    "redeem_evaluation_launch_ticket",
    "validate_evaluation_workspace_session",
]
