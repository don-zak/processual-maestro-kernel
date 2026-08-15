from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request


_ADMIN_DOM_CONTRACT_SCRIPT = (
    b'<script src="/console/js/admin_external_evaluation_dom_contract.js?v=admindomcontract01"></script>'
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path

        if path in {"/admin", "/admin/"}:
            response = await self._inject_admin_dom_contract(response)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if path == "/admin" or path == "/admin/" or (
            path.startswith("/console/js/") and path.rsplit("/", 1)[-1].startswith("admin_")
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    async def _inject_admin_dom_contract(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        chunks: list[bytes] = []
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None:
            async for chunk in body_iterator:
                chunks.append(chunk.encode("utf-8") if isinstance(chunk, str) else chunk)
            body = b"".join(chunks)
        else:
            body = bytes(getattr(response, "body", b""))

        if _ADMIN_DOM_CONTRACT_SCRIPT not in body:
            if b"</body>" in body:
                body = body.replace(
                    b"</body>", _ADMIN_DOM_CONTRACT_SCRIPT + b"</body>", 1
                )
            else:
                body += _ADMIN_DOM_CONTRACT_SCRIPT

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )
