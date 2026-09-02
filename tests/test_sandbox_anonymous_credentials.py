from __future__ import annotations

import asyncio

import pytest

from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxCredentialEnvelope,
    SandboxExecutionError,
    _safe_credential_headers,
)
from processual_api.integrations.sandbox_operational_readiness import SandboxSecretReference
from processual_api.integrations.sandbox_secret_resolution import ReferenceSandboxCredentialResolver


def test_explicit_anonymous_public_reference_resolves_without_secret_material() -> None:
    reference = SandboxSecretReference(
        binding_id="evaluation.crm.public",
        provider_id="anonymous",
        secret_reference="public",
    )

    envelope = asyncio.run(
        ReferenceSandboxCredentialResolver(reference).resolve(
            credential_profile_id="enterprise_core_api_reference",
            binding_id="evaluation.crm.public",
        )
    )

    assert envelope.source == "anonymous_public_sandbox"
    assert envelope.headers == {}
    assert _safe_credential_headers(envelope) == {}


def test_empty_credentials_from_any_other_source_remain_fail_closed() -> None:
    with pytest.raises(
        SandboxExecutionError,
        match="sandbox_credential_reference_unresolved",
    ):
        _safe_credential_headers(
            SandboxCredentialEnvelope(
                headers={},
                source="customer_secret_reference",
            )
        )


def test_anonymous_provider_with_non_public_reference_remains_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("MAESTRO_SANDBOX_AUTHORIZATION_REF_ANONYMOUS_PRIVATE", raising=False)
    monkeypatch.delenv("MAESTRO_SANDBOX_API_KEY_REF_ANONYMOUS_PRIVATE", raising=False)
    reference = SandboxSecretReference(
        binding_id="evaluation.crm.public",
        provider_id="anonymous",
        secret_reference="private",
    )

    with pytest.raises(
        SandboxExecutionError,
        match="sandbox_secret_reference_unresolved",
    ):
        asyncio.run(
            ReferenceSandboxCredentialResolver(reference).resolve(
                credential_profile_id="enterprise_core_api_reference",
                binding_id="evaluation.crm.public",
            )
        )
