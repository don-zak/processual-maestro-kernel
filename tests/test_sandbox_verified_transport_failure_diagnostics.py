from __future__ import annotations

import asyncio

import httpx

from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport


class _PeerStream:
    def get_extra_info(self, name: str):
        if name == "server_addr":
            return ("198.51.100.44", 443)
        return None


class _FailureTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={
                "Retry-After": "17",
                "Server": "edge-test",
                "Via": "gateway-test",
                "X-Request-ID": "req-safe-123",
                "Set-Cookie": "secret-cookie=must-not-leak",
                "Authorization": "Bearer must-not-leak",
            },
            content=b'{"secret":"must-not-leak"}',
            extensions={"network_stream": _PeerStream()},
        )


def test_failed_verified_peer_keeps_only_allowlisted_safe_metadata(monkeypatch) -> None:
    async def resolved(hostname: str, port: int):
        assert hostname == "sandbox.example.test"
        assert port == 443
        return ("198.51.100.44",)

    monkeypatch.setattr(
        "processual_api.integrations.sandbox_verified_transport.resolve_public_addresses",
        resolved,
    )
    transport = VerifiedPeerSandboxTransport(_FailureTransport())
    response = asyncio.run(
        transport.handle_async_request(httpx.Request("GET", "https://sandbox.example.test/users/1"))
    )

    assert response.status_code == 429
    assert transport.last_verified_peer == "198.51.100.44"
    assert transport.last_response_diagnostics == {
        "status_code": 429,
        "verified_peer": "198.51.100.44",
        "headers": {
            "retry-after": "17",
            "server": "edge-test",
            "via": "gateway-test",
            "x-request-id": "req-safe-123",
        },
        "body_included": False,
        "credential_material_included": False,
    }
    serialized = repr(transport.last_response_diagnostics)
    assert "must-not-leak" not in serialized
    assert "set-cookie" not in serialized.lower()
    assert "authorization" not in serialized.lower()


def test_safe_failure_diagnostics_do_not_change_response_contract(monkeypatch) -> None:
    async def resolved(hostname: str, port: int):
        return ("198.51.100.44",)

    monkeypatch.setattr(
        "processual_api.integrations.sandbox_verified_transport.resolve_public_addresses",
        resolved,
    )
    transport = VerifiedPeerSandboxTransport(_FailureTransport())
    response = asyncio.run(
        transport.handle_async_request(httpx.Request("GET", "https://sandbox.example.test/users/1"))
    )

    assert response.content == b'{"secret":"must-not-leak"}'
    assert response.extensions["sandbox_peer_verified"] is True
    assert response.extensions["sandbox_peer_address"] == "198.51.100.44"
