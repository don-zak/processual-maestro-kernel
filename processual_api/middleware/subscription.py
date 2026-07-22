"""Subscription middleware - enforces billing status on every request.

Stages:
  active       -> full access
  grace        -> read-only (days 0-7 after failed payment)
  suspended    -> billing page only (days 8-90)
  expired      -> blocked (after 90 days, auto-cancel)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_GRACE_DAYS = 7
_SUSPENSION_DAYS = 90

_PUBLIC_PATHS = {
    "/login",
    "/auth/token",
    "/auth/login",
    "/auth/session/refresh",
    "/auth/session/logout",
    "/auth/session/logout-all",
    "/health/live",
    "/health/ready",
    "/auth/registration/config",
    "/auth/register",
    "/auth/register/organization",
    "/auth/verify-email",
    "/auth/verification/resend",
    "/auth/mfa/status",
    "/auth/mfa/totp/enroll",
    "/auth/mfa/totp/confirm",
    "/auth/mfa/verify",
    "/auth/mfa/recovery-codes/regenerate",
    "/auth/mfa/disable",
    "/applications/demo/check",
    "/billing/webhook",
    "/docs",
    "/redoc",
    "/metrics",
    "/openapi.json",
    "/",
    "/favicon.ico",
}

_SUSPENSION_ALLOWED_PREFIXES = {"/billing"}

_READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}

_JWT_SECRET = None
_JWT_ALGORITHM = "HS256"


def _load_subscriptions() -> list[dict]:
    path = _DATA_DIR / "subscriptions.json"
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError, OSError:
            pass
    return []


def _extract_user_id(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]

    jwt_secret = _JWT_SECRET
    if jwt_secret is None:
        from ..settings import settings as _s

        globals()["_JWT_SECRET"] = _s.jwt_secret
        jwt_secret = _s.jwt_secret

    try:
        import jwt

        payload = jwt.decode(token, jwt_secret, algorithms=[_JWT_ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


def _compute_stage(sub: dict) -> str:
    status = sub.get("status", "active")
    if status == "active":
        return "active"
    if status == "expired" or status == "cancelled":
        return "expired"

    created_str = sub.get("suspended_at") or sub.get("created_at", "")
    try:
        suspended_at = datetime.fromisoformat(created_str)
    except ValueError, TypeError:
        return "grace"

    now = datetime.now(UTC)
    days_since = (now - suspended_at).days

    if days_since <= _GRACE_DAYS:
        return "grace"
    elif days_since <= _SUSPENSION_DAYS:
        return "suspended"
    else:
        return "expired"


def _get_user_sub(user_id: str) -> dict | None:
    subs = _load_subscriptions()
    user_subs = [s for s in subs if s.get("user_id") == user_id]
    if not user_subs:
        return None
    return max(user_subs, key=lambda s: s.get("created_at", ""))


class SubscriptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _PUBLIC_PATHS or path.startswith("/static/") or path.startswith("/console/"):
            return await call_next(request)

        user_id = _extract_user_id(request)
        if user_id is None:
            return await call_next(request)

        sub = _get_user_sub(user_id)
        if sub is None:
            return await call_next(request)

        stage = _compute_stage(sub)

        if stage == "active":
            return await call_next(request)

        if stage == "grace":
            if request.method not in _READ_ONLY_METHODS:
                return Response(
                    status_code=403,
                    content=json.dumps(
                        {
                            "detail": (
                                "Payment overdue - service is in read-only mode. Update billing to restore full access."
                            ),
                            "subscription_stage": "grace",
                        }
                    ),
                    media_type="application/json",
                )
            return await call_next(request)

        if stage == "suspended":
            if not any(path.startswith(p) for p in _SUSPENSION_ALLOWED_PREFIXES):
                return Response(
                    status_code=403,
                    content=json.dumps(
                        {
                            "detail": "Subscription suspended. Visit Billing to reactivate.",
                            "subscription_stage": "suspended",
                        }
                    ),
                    media_type="application/json",
                )
            return await call_next(request)

        if stage == "expired":
            return Response(
                status_code=403,
                content=json.dumps(
                    {
                        "detail": "Subscription expired after 90 days - please re-subscribe.",
                        "subscription_stage": "expired",
                    }
                ),
                media_type="application/json",
            )

        return await call_next(request)
