"""Server-owned source identity attestation for endpoint discovery evidence.

Content pinning and source identity are intentionally separate properties. A
caller can prove that a submitted API description matches an immutable digest or
revision, but that alone does not prove who published it. Source identity becomes
verified only when the exact reference/revision/content digest tuple matches a
server-maintained trusted record acquired through an out-of-band reviewed path.

The default registry is empty by design. This module never upgrades a caller
claim into provider/operator identity and never grants runtime or production
authority.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrustedEndpointSourceRecord:
    source_identity_id: str
    contract_family: str
    source_reference: str
    source_kind: str
    source_revision: str
    source_sha256: str
    policy_version: str = "r1"


@dataclass(frozen=True, slots=True)
class EndpointSourceIdentityAttestation:
    source_identity_id: str | None
    source_identity_verified: bool
    source_identity_policy_version: str | None
    source_identity_verification_method: str
    production_allowed: bool = False
    runtime_connector_approved: bool = False


# Deliberately empty until an administrator-controlled acquisition/review process
# registers an exact source tuple. Do not add providers here from request data.
TRUSTED_ENDPOINT_SOURCES: tuple[TrustedEndpointSourceRecord, ...] = ()


def _normalized(value: str) -> str:
    return str(value or "").strip().lower()


def attest_endpoint_source_identity(
    *,
    source_reference: str,
    source_kind: str,
    source_revision: str,
    source_sha256: str,
    contract_family: str,
    trusted_sources: Iterable[TrustedEndpointSourceRecord] | None = None,
) -> EndpointSourceIdentityAttestation:
    """Attest publisher/source identity only from an exact server-owned record."""

    reference = _normalized(source_reference)
    kind = _normalized(source_kind)
    revision = _normalized(source_revision)
    digest = _normalized(source_sha256)
    family = _normalized(contract_family).replace("-", "_")
    registry = TRUSTED_ENDPOINT_SOURCES if trusted_sources is None else tuple(trusted_sources)

    for record in registry:
        if _normalized(record.contract_family).replace("-", "_") != family:
            continue
        if _normalized(record.source_kind) != kind:
            continue
        if not hmac.compare_digest(_normalized(record.source_reference), reference):
            continue
        if not hmac.compare_digest(_normalized(record.source_revision), revision):
            continue
        if not hmac.compare_digest(_normalized(record.source_sha256), digest):
            continue
        return EndpointSourceIdentityAttestation(
            source_identity_id=record.source_identity_id,
            source_identity_verified=True,
            source_identity_policy_version=record.policy_version,
            source_identity_verification_method="server_trusted_exact_tuple",
        )

    return EndpointSourceIdentityAttestation(
        source_identity_id=None,
        source_identity_verified=False,
        source_identity_policy_version=None,
        source_identity_verification_method="unverified",
    )


__all__ = [
    "EndpointSourceIdentityAttestation",
    "TRUSTED_ENDPOINT_SOURCES",
    "TrustedEndpointSourceRecord",
    "attest_endpoint_source_identity",
]
