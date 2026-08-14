"""Transport wrapper that verifies the connected sandbox peer against public DNS."""

from __future__ import annotations

from typing import Any

import httpx

from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxExecutionError,
    resolve_public_addresses,
)


class VerifiedPeerSandboxTransport(httpx.AsyncBaseTransport):
    """Fail closed unless the connected peer is a pre-resolved public address."""

    def __init__(self, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._inner = inner or httpx.AsyncHTTPTransport()
        self.last_verified_peer: str | None = None

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
        response.extensions["sandbox_peer_verified"] = True
        response.extensions["sandbox_peer_address"] = peer
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


__all__ = ["VerifiedPeerSandboxTransport"]
