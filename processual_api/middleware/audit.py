from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..settings import settings

logger = logging.getLogger("processual.audit")
_AUDIT_LOG = logging.getLogger("processual.audit.trail")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.audit_enabled:
            return await call_next(request)
        start = time.time()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response: Response = await call_next(request)
        elapsed = time.time() - start
        audit_record = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_seconds": round(elapsed, 4),
            "client_host": request.client.host if request.client else "unknown",
        }
        _AUDIT_LOG.info(json.dumps(audit_record))
        return response
