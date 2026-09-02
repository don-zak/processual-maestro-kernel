"""Customer-scoped secret-reference resolution for sandbox execution.

The settings surface stores references only. Providers resolve transient headers at
execution time and may be replaced by a Vault/Secret Manager implementation.
Public sandbox endpoints may opt into the explicit ``anonymous/public`` reference,
which yields no credential material and is never inferred for other providers.
"""

from __future__ import annotations

import os
import re
from typing import Protocol

from processual_api.integrations.enterprise_sandbox_execution import (
    SandboxCredentialEnvelope,
    SandboxExecutionError,
)
from processual_api.integrations.sandbox_operational_readiness import SandboxSecretReference

_SAFE_ENV = re.compile(r"[^A-Z0-9]+")
_ANONYMOUS_PROVIDER_ID = "anonymous"
_ANONYMOUS_SECRET_REFERENCE = "public"
_ANONYMOUS_SOURCE = "anonymous_public_sandbox"


class SandboxSecretProvider(Protocol):
    async def resolve(
        self,
        *,
        provider_id: str,
        secret_reference: str,
        binding_id: str,
    ) -> SandboxCredentialEnvelope: ...


class EnvironmentReferenceSecretProvider:
    """Sandbox deployment provider keyed by customer-specific secret reference."""

    @staticmethod
    def _suffix(provider_id: str, secret_reference: str) -> str:
        raw = f"{provider_id}_{secret_reference}".strip().upper()
        value = _SAFE_ENV.sub("_", raw).strip("_")
        if not value:
            raise SandboxExecutionError("sandbox_secret_reference_invalid")
        return value

    async def resolve(
        self,
        *,
        provider_id: str,
        secret_reference: str,
        binding_id: str,
    ) -> SandboxCredentialEnvelope:
        del binding_id
        normalized_provider = str(provider_id or "").strip().lower()
        normalized_reference = str(secret_reference or "").strip().lower()
        if (
            normalized_provider == _ANONYMOUS_PROVIDER_ID
            and normalized_reference == _ANONYMOUS_SECRET_REFERENCE
        ):
            return SandboxCredentialEnvelope(headers={}, source=_ANONYMOUS_SOURCE)

        suffix = self._suffix(provider_id, secret_reference)
        authorization = os.getenv(
            f"MAESTRO_SANDBOX_AUTHORIZATION_REF_{suffix}",
            "",
        ).strip()
        api_key = os.getenv(
            f"MAESTRO_SANDBOX_API_KEY_REF_{suffix}",
            "",
        ).strip()
        headers: dict[str, str] = {}
        if authorization:
            headers["Authorization"] = authorization
        if api_key:
            headers["X-API-Key"] = api_key
        if not headers:
            raise SandboxExecutionError("sandbox_secret_reference_unresolved")
        return SandboxCredentialEnvelope(
            headers=headers,
            source="customer_secret_reference",
        )


class ReferenceSandboxCredentialResolver:
    """Resolve one stored customer secret reference through an injected provider."""

    def __init__(
        self,
        reference: SandboxSecretReference,
        *,
        provider: SandboxSecretProvider | None = None,
    ) -> None:
        self._reference = reference
        self._provider = provider or EnvironmentReferenceSecretProvider()

    async def resolve(
        self,
        *,
        credential_profile_id: str,
        binding_id: str,
    ) -> SandboxCredentialEnvelope:
        del credential_profile_id
        if binding_id != self._reference.binding_id:
            raise SandboxExecutionError("sandbox_secret_reference_binding_mismatch")
        return await self._provider.resolve(
            provider_id=self._reference.provider_id,
            secret_reference=self._reference.secret_reference,
            binding_id=binding_id,
        )


__all__ = [
    "EnvironmentReferenceSecretProvider",
    "ReferenceSandboxCredentialResolver",
    "SandboxSecretProvider",
]
