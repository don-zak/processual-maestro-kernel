from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from prometheus_client import Counter, Histogram

    REQUESTS_TOTAL = Counter("processual_requests_total", "Total HTTP requests", ["method", "endpoint"])
    REQUEST_LATENCY = Histogram("processual_request_latency_seconds", "HTTP request latency", ["method", "endpoint"])
    _prometheus_available = True
except Exception:
    _prometheus_available = False


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _prometheus_available:
            return await call_next(request)
        start = time.time()
        response: Response = await call_next(request)
        latency = time.time() - start
        endpoint = request.url.path
        REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(latency)
        return response
