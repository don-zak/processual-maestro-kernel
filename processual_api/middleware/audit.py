from __future__ import annotations

import json
import logging
import re
import time

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
        response: Response = await call_next(request)
        elapsed = time.time() - start
        response_request_id = response.headers.get("X-Request-ID", "")
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = next(
            (
                value
                for value in (response_request_id, supplied_request_id)
                if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value)
            ),
            "unavailable",
        )
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
