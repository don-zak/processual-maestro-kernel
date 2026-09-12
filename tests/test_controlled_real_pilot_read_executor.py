from __future__ import annotations

import asyncio

import httpx
import pytest

from processual_api.services.controlled_real_pilot import ControlledRealPilotGrant
from processual_api.services.controlled_real_pilot_read_executor import (
    ControlledRealPilotReadError,
    execute_controlled_real_read,
)


class _VerifiedMockTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, status: int = 200, body: bytes = b'{"ok":true}', content_type: str = "application/json") -> None:
        self.status = status
        self.body = body
        self.content_type = content_type
        self.last_verified_peer: str | None = None
        self.seen_method: str | None = None
        self.seen_url: str | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.seen_method = request.method
        self.seen_url = str(request.url)
        self.last_verified_peer = "203.0.113.20"
        return httpx.Response(
            self.status,
            headers={"content-type": self.content_type},
            content=self.body,
            request=request,
        )


class _UnverifiedMockTransport(_VerifiedMockTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await super().handle_async_request(request)
        self.last_verified_peer = None
        return response


def _grant() -> ControlledRealPilotGrant:
    return ControlledRealPilotGrant(
        grant_id="pilot-grant-1",
        task_id="crm.customer_context",
        binding_id="real.crm.customer_context",
        destination_host="crm.example.com",
        method="GET",
        operation_class="read",
        resource_ids=frozenset({"customer-1"}),
        writable_fields=frozenset(),
        max_mutations=0,
    )


def _enable_read(monkeypatch) -> None:
    monkeypatch.setenv("MAESTRO_CONTROLLED_REAL_PILOT_ENABLED", "true")
    monkeypatch.setenv("MAESTRO_CONTROLLED_REAL_PILOT_READS_ENABLED", "true")
    monkeypatch.setenv("MAESTRO_CONTROLLED_REAL_PILOT_KILL_SWITCH", "false")


def test_real_read_executor_uses_get_only_and_returns_hashes(monkeypatch) -> None:
    _enable_read(monkeypatch)
    transport = _VerifiedMockTransport()

    result = asyncio.run(
        execute_controlled_real_read(
            _grant(),
            task_id="crm.customer_context",
            binding_id="real.crm.customer_context",
            destination_host="crm.example.com",
            resource_id="customer-1",
            path="/customers/1",
            credential_headers={"Authorization": "Bearer hidden"},
            transport=transport,
        )
    )

    assert transport.seen_method == "GET"
    assert transport.seen_url == "https://crm.example.com/customers/1"
    assert result["status"] == "controlled_real_pilot_read_succeeded"
    assert result["production_read_performed"] is True
    assert result["production_mutation_performed"] is False
    assert result["raw_response_included"] is False
    assert result["credential_material_included"] is False
    assert result["external_evaluation_authority_reused"] is False
    assert len(result["response_sha256"]) == 64
    assert len(result["payload_sha256"]) == 64
    assert len(result["evidence_sha256"]) == 64


def test_executor_is_disabled_without_separate_pilot_switches(monkeypatch) -> None:
    monkeypatch.delenv("MAESTRO_CONTROLLED_REAL_PILOT_ENABLED", raising=False)
    monkeypatch.delenv("MAESTRO_CONTROLLED_REAL_PILOT_READS_ENABLED", raising=False)
    monkeypatch.delenv("MAESTRO_CONTROLLED_REAL_PILOT_KILL_SWITCH", raising=False)

    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_disabled"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1",
                transport=_VerifiedMockTransport(),
            )
        )


def test_executor_rejects_unverified_peer(monkeypatch) -> None:
    _enable_read(monkeypatch)
    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_peer_unverified"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1",
                transport=_UnverifiedMockTransport(),
            )
        )


def test_executor_blocks_redirects(monkeypatch) -> None:
    _enable_read(monkeypatch)
    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_redirect_blocked"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1",
                transport=_VerifiedMockTransport(status=302),
            )
        )


def test_executor_rejects_non_json(monkeypatch) -> None:
    _enable_read(monkeypatch)
    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_response_not_json"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1",
                transport=_VerifiedMockTransport(content_type="text/html", body=b"<html></html>"),
            )
        )


def test_executor_rejects_query_fragment_and_non_allowlisted_credential_header(monkeypatch) -> None:
    _enable_read(monkeypatch)
    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_query_or_fragment_not_allowed"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1?expand=all",
                transport=_VerifiedMockTransport(),
            )
        )

    with pytest.raises(ControlledRealPilotReadError, match="controlled_real_pilot_credential_header_not_allowed"):
        asyncio.run(
            execute_controlled_real_read(
                _grant(),
                task_id="crm.customer_context",
                binding_id="real.crm.customer_context",
                destination_host="crm.example.com",
                resource_id="customer-1",
                path="/customers/1",
                credential_headers={"Cookie": "secret"},
                transport=_VerifiedMockTransport(),
            )
        )
