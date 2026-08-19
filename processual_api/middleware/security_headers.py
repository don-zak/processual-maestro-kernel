from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_ADMIN_DOM_CONTRACT_SCRIPT = (
    b'<script src="/console/js/admin_external_evaluation_dom_contract.js?v=admindomcontract01"></script>'
)
_PUBLIC_AUTHORITY_REPLACEMENTS = (
    (b"Production Ready", b"Qualification Build"),
    ("جاهز للإنتاج".encode(), "نسخة تأهيل".encode()),
    (b"v2.0.0 \xe2\x80\x94 production", b"v2.0.0 \xe2\x80\x94 qualification"),
)
_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "manifest-src 'self'",
        "media-src 'self'",
        "worker-src 'self'",
        "upgrade-insecure-requests",
    )
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path

        if path in {"/", "/console", "/console/", "/console/index.html"}:
            response = await self._rewrite_public_authority_claims(response)

        if path in {"/admin", "/admin/"}:
            response = await self._inject_admin_dom_contract(response)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY

        if path == "/admin" or path == "/admin/" or (
            path.startswith("/console/js/")
            and path.rsplit("/", 1)[-1].startswith("admin_")
        ):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    async def _rewrite_public_authority_claims(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        for source, replacement in _PUBLIC_AUTHORITY_REPLACEMENTS:
            body = body.replace(source, replacement)
        return self._rebuilt_response(response, body)

    async def _inject_admin_dom_contract(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        if _ADMIN_DOM_CONTRACT_SCRIPT not in body:
            if b"</body>" in body:
                body = body.replace(
                    b"</body>", _ADMIN_DOM_CONTRACT_SCRIPT + b"</body>", 1
                )
            else:
                body += _ADMIN_DOM_CONTRACT_SCRIPT
        return self._rebuilt_response(response, body)

    async def _response_body(self, response: Response) -> bytes:
        chunks: list[bytes] = []
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is not None:
            async for chunk in body_iterator:
                chunks.append(chunk.encode("utf-8") if isinstance(chunk, str) else chunk)
            return b"".join(chunks)
        return bytes(getattr(response, "body", b""))

    def _rebuilt_response(self, response: Response, body: bytes) -> Response:
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )
