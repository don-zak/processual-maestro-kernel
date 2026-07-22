from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..cache.redis import get_redis, rate_limit_key
from ..settings import settings

_AUTHORITATIVE_IDENTITY_PATHS = {
    "/auth/register",
    "/auth/register/organization",
}


def _parse_rate_limit(limit_str: str) -> tuple[int, int]:
    parts = limit_str.strip().split("/")
    count = int(parts[0])
    unit = parts[1] if len(parts) > 1 else "minute"
    windows = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
    return count, windows.get(unit, 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in _AUTHORITATIVE_IDENTITY_PATHS:
            return await call_next(request)
        if not settings.rate_limit_enabled:
            return await call_next(request)

        redis = await get_redis()
        if redis is None:
            return await call_next(request)

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        identifier = client_ip

        auth_header = request.headers.get("Authorization", "")
        limit_str = (
            settings.rate_limit_authenticated if auth_header.startswith("Bearer ") else settings.rate_limit_default
        )

        max_requests, window = _parse_rate_limit(limit_str)
        key = rate_limit_key(identifier, request.url.path)

        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window)

            if current > max_requests:
                ttl = await redis.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later.", "retry_after": max(ttl, 0)},
                    headers={
                        "Retry-After": str(max(ttl, 0)),
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )
        except Exception:
            return await call_next(request)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, max_requests - current))
        return response
