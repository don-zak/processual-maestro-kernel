from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from processual_api.integrations.enterprise_sandbox_execution import SandboxExecutionError
from processual_api.integrations.sandbox_operational_readiness import (
    SANDBOX_CONTENT_STORAGE_KEY,
    SANDBOX_SECRET_REFERENCE_STORAGE_KEY,
    SandboxContentContract,
    SandboxSecretReference,
    evaluate_sandbox_operational_readiness,
)
from processual_api.integrations.sandbox_secret_resolution import (
    EnvironmentReferenceSecretProvider,
    ReferenceSandboxCredentialResolver,
)
from processual_api.integrations.sandbox_verified_transport import VerifiedPeerSandboxTransport
from processual_api.routers import settings_enterprise_sandbox_operational_runtime as runtime

_PROVISIONING_SHA = "p" * 64


def _content(binding_id: str = "billing.account") -> SandboxContentContract:
    return SandboxContentContract(
        binding_id=binding_id,
        dataset_reference="customer_acme_sandbox_dataset_v1",
        fixture_profile_reference="billing_accounts_happy_path_v1",
        required_record_types=("account", "invoice"),
        acceptance_criteria_references=("billing_read_contract_v1",),
    )


def _secret(binding_id: str = "billing.account") -> SandboxSecretReference:
    return SandboxSecretReference(
        binding_id=binding_id,
        provider_id="customer_vault",
        secret_reference="acme/billing/sandbox-reader",
    )


def _proof() -> dict[str, object]:
    return {
        "binding_id": "billing.account",
        "task_id": "billing.account_context",
        "operational_proof": True,
        "peer_address_verified": True,
        "customer_secret_reference_configured": True,
        "network_request_executed": True,
        "mapping_valid": True,
        "ready_for_task_consumption": True,
        "provisioning_sha256": _PROVISIONING_SHA,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "evidence_sha256": "a" * 64,
    }


def test_content_contract_accepts_references_only() -> None:
    contract = _content()
    assert contract.customer_owned is True
    assert contract.synthetic_or_nonproduction is True
    assert contract.secrets_included is False
    assert contract.raw_payloads_included is False

    with pytest.raises(ValidationError, match="references only"):
        SandboxContentContract(
            binding_id="billing.account",
            dataset_reference="https://customer.example/data.json",
            fixture_profile_reference="billing",
            required_record_types=("account",),
            acceptance_criteria_references=("acceptance",),
        )

    with pytest.raises(ValidationError, match="cannot contain secrets or raw payloads"):
        SandboxContentContract(
            binding_id="billing.account",
            dataset_reference="dataset_ref",
            fixture_profile_reference="fixture_ref",
            required_record_types=("account",),
            acceptance_criteria_references=("acceptance",),
            raw_payloads_included=True,
        )


def test_secret_reference_rejects_secret_material() -> None:
    reference = _secret()
    assert reference.customer_scoped is True
    assert reference.value_included is False

    with pytest.raises(ValidationError, match="references only"):
        SandboxSecretReference(
            binding_id="billing.account",
            provider_id="customer_vault",
            secret_reference="token=should-not-be-here",
        )

    with pytest.raises(ValidationError, match="cannot include secret values"):
        SandboxSecretReference(
            binding_id="billing.account",
            provider_id="customer_vault",
            secret_reference="acme/billing/sandbox-reader",
            value_included=True,
        )


def test_readiness_is_fail_closed_until_all_operational_proofs_exist() -> None:
    initial = evaluate_sandbox_operational_readiness(
        binding_configured=False,
        mapping_configured=False,
        secret_reference=None,
        content_contract=None,
        live_proof_evidence=None,
    )
    assert initial["status"] == "not_configured"
    assert initial["sandbox_ready"] is False
    assert "endpoint_binding_required" in initial["blocker_codes"]

    provisioned = evaluate_sandbox_operational_readiness(
        binding_configured=True,
        mapping_configured=True,
        secret_reference=_secret(),
        content_contract=_content(),
        live_proof_evidence=None,
        expected_provisioning_sha256=_PROVISIONING_SHA,
    )
    assert provisioned["status"] == "content_ready"
    assert provisioned["sandbox_ready"] is False
    assert provisioned["blocker_codes"] == ["hardened_live_sandbox_proof_required"]

    ready = evaluate_sandbox_operational_readiness(
        binding_configured=True,
        mapping_configured=True,
        secret_reference=_secret(),
        content_contract=_content(),
        live_proof_evidence=_proof(),
        expected_provisioning_sha256=_PROVISIONING_SHA,
    )
    assert ready["status"] == "sandbox_ready"
    assert ready["sandbox_ready"] is True
    assert ready["blocker_codes"] == []
    assert ready["production_allowed"] is False
    assert ready["runtime_connector_approved"] is False


def test_changed_provisioning_invalidates_existing_proof() -> None:
    result = evaluate_sandbox_operational_readiness(
        binding_configured=True,
        mapping_configured=True,
        secret_reference=_secret(),
        content_contract=_content(),
        live_proof_evidence=_proof(),
        expected_provisioning_sha256="q" * 64,
    )
    assert result["status"] == "content_ready"
    assert result["sandbox_ready"] is False
    assert result["blocker_codes"] == ["hardened_live_sandbox_proof_required"]


def test_legacy_live_proof_cannot_mark_operational_sandbox_ready() -> None:
    legacy = _proof()
    legacy.pop("operational_proof")
    legacy.pop("peer_address_verified")
    legacy.pop("customer_secret_reference_configured")
    result = evaluate_sandbox_operational_readiness(
        binding_configured=True,
        mapping_configured=True,
        secret_reference=_secret(),
        content_contract=_content(),
        live_proof_evidence=legacy,
        expected_provisioning_sha256=_PROVISIONING_SHA,
    )
    assert result["status"] == "content_ready"
    assert result["sandbox_ready"] is False
    assert result["blocker_codes"] == ["hardened_live_sandbox_proof_required"]


def test_reference_resolver_is_customer_scoped(monkeypatch) -> None:
    monkeypatch.setenv(
        "MAESTRO_SANDBOX_AUTHORIZATION_REF_CUSTOMER_VAULT_ACME_BILLING_SANDBOX_READER",
        "Bearer transient-test-value",
    )
    resolver = ReferenceSandboxCredentialResolver(_secret())
    envelope = asyncio.run(
        resolver.resolve(
            credential_profile_id="enterprise_core_api_reference",
            binding_id="billing.account",
        )
    )
    assert envelope.source == "customer_secret_reference"
    assert envelope.headers == {"Authorization": "Bearer transient-test-value"}
    assert "transient-test-value" not in repr(envelope)

    with pytest.raises(SandboxExecutionError, match="binding_mismatch"):
        asyncio.run(
            resolver.resolve(
                credential_profile_id="enterprise_core_api_reference",
                binding_id="other.binding",
            )
        )


def test_environment_reference_provider_requires_resolvable_reference(monkeypatch) -> None:
    provider = EnvironmentReferenceSecretProvider()
    monkeypatch.delenv(
        "MAESTRO_SANDBOX_AUTHORIZATION_REF_CUSTOMER_VAULT_ACME_BILLING_SANDBOX_READER",
        raising=False,
    )
    monkeypatch.delenv(
        "MAESTRO_SANDBOX_API_KEY_REF_CUSTOMER_VAULT_ACME_BILLING_SANDBOX_READER",
        raising=False,
    )
    with pytest.raises(SandboxExecutionError, match="secret_reference_unresolved"):
        asyncio.run(
            provider.resolve(
                provider_id="customer_vault",
                secret_reference="acme/billing/sandbox-reader",
                binding_id="billing.account",
            )
        )


class _PeerStream:
    def __init__(self, address: str) -> None:
        self._address = address

    def get_extra_info(self, name: str):
        if name == "server_addr":
            return (self._address, 443)
        return None


class _PeerTransport(httpx.AsyncBaseTransport):
    def __init__(self, address: str) -> None:
        self._address = address

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True},
            extensions={"network_stream": _PeerStream(self._address)},
        )


@pytest.mark.parametrize("peer", ["198.51.100.44", "2001:db8::44"])
def test_verified_peer_transport_accepts_resolved_peer(monkeypatch, peer: str) -> None:
    async def resolved(hostname: str, port: int):
        assert hostname == "sandbox.example.test"
        assert port == 443
        return (peer,)

    monkeypatch.setattr(
        "processual_api.integrations.sandbox_verified_transport.resolve_public_addresses",
        resolved,
    )
    transport = VerifiedPeerSandboxTransport(_PeerTransport(peer))
    response = asyncio.run(
        transport.handle_async_request(httpx.Request("GET", "https://sandbox.example.test/v1"))
    )
    assert response.status_code == 200
    assert transport.last_verified_peer == peer
    assert response.extensions["sandbox_peer_verified"] is True


def test_verified_peer_transport_rejects_peer_mismatch(monkeypatch) -> None:
    async def resolved(hostname: str, port: int):
        return ("198.51.100.44",)

    monkeypatch.setattr(
        "processual_api.integrations.sandbox_verified_transport.resolve_public_addresses",
        resolved,
    )
    transport = VerifiedPeerSandboxTransport(_PeerTransport("198.51.100.45"))
    with pytest.raises(SandboxExecutionError, match="peer_address_mismatch"):
        asyncio.run(
            transport.handle_async_request(
                httpx.Request("GET", "https://sandbox.example.test/v1")
            )
        )


def test_readiness_route_reports_operational_state(monkeypatch) -> None:
    raw = {
        SANDBOX_CONTENT_STORAGE_KEY: [_content().model_dump()],
        SANDBOX_SECRET_REFERENCE_STORAGE_KEY: [_secret().model_dump()],
        runtime.binding_runtime.SANDBOX_EVIDENCE_STORAGE_KEY: [_proof()],
    }
    monkeypatch.setattr(
        runtime.binding_runtime,
        "_require_enterprise",
        lambda current_user: ("client-1", raw),
    )
    monkeypatch.setattr(
        runtime.binding_runtime,
        "_find_binding",
        lambda raw, binding_id: SimpleNamespace(
            task_id="billing.account_context",
            method="GET",
            field_mapping={"account_id": "$.id"},
        ),
    )
    monkeypatch.setattr(
        runtime.binding_runtime,
        "_find_request_mapping",
        lambda raw, binding_id: None,
    )
    monkeypatch.setattr(
        runtime,
        "_provisioning_sha256",
        lambda **kwargs: _PROVISIONING_SHA,
    )
    result = asyncio.run(
        runtime.get_enterprise_sandbox_operational_readiness(
            "billing.account",
            current_user={"user_id": "client-1"},
        )
    )
    assert result["status"] == "sandbox_ready"
    assert result["sandbox_ready"] is True
    assert result["provisioning_sha256"] == _PROVISIONING_SHA
    assert result["secret_reference"]["value_included"] is False
    assert result["raw_secret_visible"] is False
    assert result["raw_payload_visible"] is False


def test_operational_execution_requires_content_and_secret_reference(monkeypatch) -> None:
    raw: dict[str, object] = {}
    monkeypatch.setattr(
        runtime.binding_runtime,
        "_require_enterprise",
        lambda current_user: ("client-1", raw),
    )
    monkeypatch.setattr(
        runtime.binding_runtime,
        "_find_binding",
        lambda raw, binding_id: SimpleNamespace(binding_id=binding_id),
    )
    body = runtime.binding_runtime.EndpointSandboxExecuteRequest(
        task_input={"account_id": "A-100"}
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            runtime.execute_enterprise_sandbox_operational_proof(
                "billing.account",
                body,
                current_user={"user_id": "client-1"},
            )
        )
    assert exc_info.value.status_code == 409
    assert "content contract" in str(exc_info.value.detail).lower()
