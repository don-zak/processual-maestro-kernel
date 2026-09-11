"""Transport wrapper that verifies the connected sandbox peer against public DNS."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxExecutionError,
    resolve_public_addresses,
)

logger = logging.getLogger(__name__)

_SAFE_DIAGNOSTIC_HEADERS = (
    "retry-after",
    "server",
    "via",
    "x-request-id",
)


class VerifiedPeerSandboxTransport(httpx.AsyncBaseTransport):
    """Fail closed unless the connected peer is a pre-resolved public address."""

    def __init__(self, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()
        self.last_verified_peer: str | None = None
        self.last_response_diagnostics: dict[str, Any] | None = None

    @staticmethod
    def _peer_address(response: httpx.Response) -> str:
        stream: Any = response.extensions.get("network_stream")
        getter = getattr(stream, "get_extra_info", None)
        if not callable(getter):
            raise SandboxExecutionError("sandbox_peer_address_unavailable")
        peer = getter("server_addr") or getter("peername")
        if isinstance(peer, (tuple, list)) and peer:
            return str(peer[0]).split("%", 1)[0]
        if isinstance(peer, str) and peer.strip():
            return peer.strip().split("%", 1)[0]
        raise SandboxExecutionError("sandbox_peer_address_unavailable")

    @staticmethod
    def _safe_response_diagnostics(response: httpx.Response, peer: str) -> dict[str, Any]:
        headers = {
            name: response.headers[name]
            for name in _SAFE_DIAGNOSTIC_HEADERS
            if name in response.headers
        }
        return {
            "status_code": int(response.status_code),
            "verified_peer": peer,
            "headers": headers,
            "body_included": False,
            "credential_material_included": False,
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        if not hostname:
            raise SandboxExecutionError("sandbox_destination_host_required")
        port = int(request.url.port or 443)
        allowed = set(await resolve_public_addresses(hostname, port))
        response = await self._inner.handle_async_request(request)
        peer = self._peer_address(response)
        if peer not in allowed:
            await response.aclose()
            raise SandboxExecutionError("sandbox_peer_address_mismatch")
        self.last_verified_peer = peer
        self.last_response_diagnostics = self._safe_response_diagnostics(response, peer)
        if response.status_code >= 400:
            logger.warning(
                "sandbox_verified_peer_http_failure host=%s status=%s peer=%s safe_headers=%s body_included=false credential_material_included=false",
                hostname,
                response.status_code,
                peer,
                self.last_response_diagnostics["headers"],
            )
        response.extensions["sandbox_peer_verified"] = True
        response.extensions["sandbox_peer_address"] = peer
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


__all__ = ["VerifiedPeerSandboxTransport"]
