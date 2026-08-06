"""Database-backed subscription access enforcement."""

from __future__ import annotations

import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from processual_api.admin_marketplace.subscription_access import (
    resolve_subscription_access,
)

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


def _json_response(*, status_code: int, detail: str, stage: str) -> Response:
    return Response(
        status_code=status_code,
        content=json.dumps(
            {
                "detail": detail,
                "subscription_stage": stage,
            }
        ),
        media_type="application/json",
    )


def _extract_customer_ref(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]

    jwt_secret = _JWT_SECRET
    if jwt_secret is None:
        from ..settings import settings as _settings

        globals()["_JWT_SECRET"] = _settings.jwt_secret
        jwt_secret = _settings.jwt_secret

    try:
        import jwt

        payload = jwt.decode(token, jwt_secret, algorithms=[_JWT_ALGORITHM])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            return None
        normalized = subject.strip().lower()
        return normalized or None
    except Exception:
        return None


class SubscriptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if (
            path in _PUBLIC_PATHS
            or path.startswith("/static/")
            or path.startswith("/console/")
        ):
            return await call_next(request)

        customer_ref = _extract_customer_ref(request)
        if customer_ref is None:
            return await call_next(request)

        try:
            access = await resolve_subscription_access(customer_ref)
        except Exception:
            return _json_response(
                status_code=503,
                detail="Subscription access is temporarily unavailable.",
                stage="unavailable",
            )

        if access is None:
            return _json_response(
                status_code=403,
                detail="No active subscription access record was found.",
                stage="inactive",
            )

        stage = access.access_stage
        if stage == "active":
            return await call_next(request)

        if stage == "grace":
            if request.method not in _READ_ONLY_METHODS:
                return _json_response(
                    status_code=403,
                    detail="Payment overdue. Service is read-only until billing is restored.",
                    stage="grace",
                )
            return await call_next(request)

        if stage == "suspended":
            if not any(path.startswith(prefix) for prefix in _SUSPENSION_ALLOWED_PREFIXES):
                return _json_response(
                    status_code=403,
                    detail="Subscription suspended. Visit Billing to reactivate.",
                    stage="suspended",
                )
            return await call_next(request)

        if stage == "terminated":
            return _json_response(
                status_code=403,
                detail="Subscription terminated. A new subscription is required.",
                stage="terminated",
            )

        return _json_response(
            status_code=503,
            detail="Subscription access is temporarily unavailable.",
            stage="unavailable",
        )
