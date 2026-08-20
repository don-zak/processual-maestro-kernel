import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


_ADMIN_DOM_CONTRACT_SCRIPT = (
    b'<script src="/console/js/admin_external_evaluation_dom_contract.js?v=admindomcontract01"></script>'
)
_VQ1_NARROW_HARDENING_STYLESHEET = (
    b'<link rel="stylesheet" href="/console/css/vq1_narrow_hardening.css?v=vq1narrow01">'
)
_VQ1_SETTINGS_OWNERSHIP_SCRIPT = (
    b'<script src="/console/js/vq1_settings_ownership.js?v=vq1ownership01"></script>'
)
_LONG_CARD_COLLAPSE_SCRIPT = (
    b'<script src="/console/js/long_card_collapse.js?v=longcards01"></script>'
)
_PUBLIC_AUTHORITY_REPLACEMENTS = (
    (b"Production Ready", b"Qualification Build"),
    ("جاهز للإنتاج".encode(), "نسخة تأهيل".encode()),
    (b"v2.0.0 \xe2\x80\x94 production", b"v2.0.0 \xe2\x80\x94 qualification"),
)
_PUBLIC_ASSET_REPLACEMENTS = (
    (
        b'https://cdn.jsdelivr.net/npm/chart.js',
        b'https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js',
    ),
)
_LEGACY_CONSOLE_SCRIPT_TAGS = (
    b'<script src="js/adapters/governor.js"></script>',
    b'<script src="js/adapters/cgt.js"></script>',
    b'<script src="js/pages/governor.js"></script>',
    b'<script src="js/pages/cgt.js"></script>',
)
_LEGACY_CONSOLE_ASSET_PATHS = {
    "/console/js/adapters/governor.js",
    "/console/js/adapters/cgt.js",
    "/console/js/pages/governor.js",
    "/console/js/pages/cgt.js",
}
_LEGACY_CONSOLE_QUARANTINE_STYLE = (
    b'<style id="legacy-console-quarantine">'
    b'[data-page="cgt"],[data-page="governor"],'
    b'#page-cgt,#page-governor{display:none!important}'
    b'</style>'
)
_LEGACY_CONSOLE_PAGE_REGIONS = (
    (b"<!-- ===== PAGE: CGT Evaluator ===== -->", b"<!-- ===== PAGE: Workflows ===== -->"),
    (b"<!-- ===== PAGE: Governor ===== -->", b"<!-- ===== PAGE: Gateway ===== -->"),
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
        path = request.url.path
        if path in _LEGACY_CONSOLE_ASSET_PATHS:
            response: Response = PlainTextResponse(
                "legacy_console_surface_quarantined",
                status_code=410,
            )
        else:
            response = await call_next(request)

        if path in {"/", "/console", "/console/", "/console/index.html"}:
            response = await self._rewrite_public_authority_claims(response)

        if path in {"/console", "/console/", "/console/index.html"}:
            response = await self._pin_public_assets(response)
            response = await self._quarantine_legacy_console_surfaces(response)
            response = await self._inject_vq1_narrow_hardening(response)
            response = await self._inject_vq1_settings_ownership(response)
            response = await self._inject_long_card_collapse(response)

        if path in {"/admin", "/admin/"}:
            response = await self._inject_admin_dom_contract(response)
            response = await self._inject_vq1_narrow_hardening(response)
            response = await self._inject_long_card_collapse(response)

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

    async def _pin_public_assets(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        for source, replacement in _PUBLIC_ASSET_REPLACEMENTS:
            body = body.replace(source, replacement)
        return self._rebuilt_response(response, body)

    async def _quarantine_legacy_console_surfaces(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        for script_tag in _LEGACY_CONSOLE_SCRIPT_TAGS:
            body = body.replace(script_tag, b"")
        body = re.sub(
            rb'<button class="nav-btn[^>]*data-page="(?:cgt|governor)"[^>]*>.*?</button>\s*',
            b"",
            body,
            flags=re.DOTALL,
        )
        for start_marker, end_marker in _LEGACY_CONSOLE_PAGE_REGIONS:
            start = body.find(start_marker)
            end = body.find(end_marker)
            if start != -1 and end != -1 and start < end:
                body = body[:start] + body[end:]
        if _LEGACY_CONSOLE_QUARANTINE_STYLE not in body:
            if b"</head>" in body:
                body = body.replace(
                    b"</head>",
                    _LEGACY_CONSOLE_QUARANTINE_STYLE + b"</head>",
                    1,
                )
            else:
                body = _LEGACY_CONSOLE_QUARANTINE_STYLE + body
        return self._rebuilt_response(response, body)

    async def _inject_vq1_narrow_hardening(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        if _VQ1_NARROW_HARDENING_STYLESHEET not in body:
            if b"</head>" in body:
                body = body.replace(
                    b"</head>",
                    _VQ1_NARROW_HARDENING_STYLESHEET + b"</head>",
                    1,
                )
            else:
                body = _VQ1_NARROW_HARDENING_STYLESHEET + body
        return self._rebuilt_response(response, body)

    async def _inject_vq1_settings_ownership(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        if _VQ1_SETTINGS_OWNERSHIP_SCRIPT not in body:
            if b"</body>" in body:
                body = body.replace(
                    b"</body>", _VQ1_SETTINGS_OWNERSHIP_SCRIPT + b"</body>", 1
                )
            else:
                body += _VQ1_SETTINGS_OWNERSHIP_SCRIPT
        return self._rebuilt_response(response, body)

    async def _inject_long_card_collapse(self, response: Response) -> Response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        body = await self._response_body(response)
        if _LONG_CARD_COLLAPSE_SCRIPT not in body:
            if b"</body>" in body:
                body = body.replace(
                    b"</body>", _LONG_CARD_COLLAPSE_SCRIPT + b"</body>", 1
                )
            else:
                body += _LONG_CARD_COLLAPSE_SCRIPT
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
