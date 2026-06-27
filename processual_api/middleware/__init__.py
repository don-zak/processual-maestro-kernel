"""Middleware package — request processing pipeline.

Exported middleware (in application order):
  - RequestIDMiddleware       — assign unique request IDs
  - RateLimitMiddleware       — per-client rate limiting via Redis
  - SecurityHeadersMiddleware — security-related response headers
  - MetricsMiddleware         — Prometheus request metrics
  - AuditMiddleware           — request/response audit logging
  - SubscriptionMiddleware    — billing subscription enforcement
  - error_handler_middleware  — global HTTP exception handler
"""

from .audit import AuditMiddleware
from .error_handler import error_handler_middleware
from .metrics import MetricsMiddleware
from .rate_limit import RateLimitMiddleware
from .request_id import RequestIDMiddleware
from .security_headers import SecurityHeadersMiddleware
from .subscription import SubscriptionMiddleware

__all__ = [
    "RequestIDMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "MetricsMiddleware",
    "AuditMiddleware",
    "SubscriptionMiddleware",
    "error_handler_middleware",
]
