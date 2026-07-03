from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..billing.usage_pricing import pricing_decision
from ..services.usage_log_store import append_usage_log


def _as_int_or_none(value: object) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _quota_usage_record(
    current_user: dict,
    *,
    units_charged: int,
) -> dict[str, object]:
    quota = current_user.get("quota")
    if not isinstance(quota, dict):
        return {}

    quota_requested = _as_int_or_none(quota.get("requested"))
    if quota_requested is None:
        quota_requested = units_charged

    quota_after = _as_int_or_none(quota.get("used"))
    quota_before = None
    if quota_after is not None:
        quota_before = max(quota_after - quota_requested, 0)

    return {
        "quota_scope": quota.get("scope", ""),
        "quota_limit": _as_int_or_none(quota.get("limit")),
        "quota_used": quota_after,
        "quota_requested": quota_requested,
        "quota_remaining": _as_int_or_none(quota.get("remaining")),
        "quota_before": quota_before,
        "quota_after": quota_after,
        "plan_id": quota.get("plan_id") or current_user.get("plan_id", ""),
    }


class UsageLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)

        current_user = getattr(request.state, "current_user", None)
        if not isinstance(current_user, dict):
            return response

        if current_user.get("auth_method") != "api_key":
            return response

        pricing_item_count = getattr(request.state, "pricing_item_count", None)
        if not isinstance(pricing_item_count, int):
            pricing_item_count = None

        pricing_record = pricing_decision(
            request.url.path,
            item_count=pricing_item_count,
        ).to_usage_record()
        pricing_record.pop("endpoint", None)
        units_charged = int(pricing_record["units_charged"])
        quota_record = _quota_usage_record(
            current_user,
            units_charged=units_charged,
        )

        append_usage_log({
            "created_at": datetime.now(UTC).isoformat(),
            "request_id": response.headers.get("X-Request-ID", request.headers.get("X-Request-ID", "")),
            "client_id": current_user.get("client_id", ""),
            "user_id": current_user.get("user_id") or current_user.get("sub", ""),
            "api_key_id": current_user.get("api_key_id", ""),
            "api_key_prefix": current_user.get("api_key_prefix", ""),
            "auth_method": current_user.get("auth_method", ""),
            "session_type": current_user.get("session_type", ""),
            "method": request.method,
            "endpoint": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "role": current_user.get("role", ""),
            **pricing_record,
            **quota_record,
        })

        return response
