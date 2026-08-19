"""Manual public-standards qualification for the reviewed CAMARA QoD source.

This runner proves only acquisition and contract quality for a public standards
artifact. It never receives provider credentials, never targets an operator
sandbox, and never grants runtime or production authority.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from processual_api.integrations.endpoint_discovery_quality import assess_endpoint_discovery
from processual_api.integrations.endpoint_source_attestation import attest_endpoint_source_identity
from processual_api.integrations.enterprise_sandbox_execution import resolve_public_addresses
from processual_api.integrations.trusted_endpoint_source_acquisition import (
    CAMARA_QOD_R32_COMMIT,
    CAMARA_QOD_R32_PATH,
    CAMARA_QOD_R32_QUALIFICATION_CANDIDATE,
    acquire_trusted_github_endpoint_source,
)


async def qualify_reviewed_camara_qod_public_source(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    resolve_host: Callable[[str, int], Awaitable[tuple[str, ...]]] = resolve_public_addresses,
) -> dict[str, Any]:
    """Acquire and assess the exact reviewed public CAMARA QoD r3.2 source."""

    candidate = CAMARA_QOD_R32_QUALIFICATION_CANDIDATE
    acquired = await acquire_trusted_github_endpoint_source(
        source_identity_id=candidate.source_identity_id,
        source_revision=CAMARA_QOD_R32_COMMIT,
        source_path=CAMARA_QOD_R32_PATH,
        catalog=(candidate,),
        transport=transport,
        resolve_host=resolve_host,
    )
    assessment = assess_endpoint_discovery(
        acquired.api_description,
        contract_family=candidate.contract_family,
        source_reference=acquired.trusted_record.source_reference,
        release_pinned=True,
        external_references_resolved=acquired.external_references_resolved,
    )
    attestation = attest_endpoint_source_identity(
        source_reference=acquired.trusted_record.source_reference,
        source_kind=acquired.trusted_record.source_kind,
        source_revision=acquired.trusted_record.source_revision,
        source_sha256=assessment["source_sha256"],
        contract_family=assessment["contract_family"],
        trusted_sources=(acquired.trusted_record,),
    )
    return {
        "status": "public_standards_source_acquired",
        "source_identity_id": attestation.source_identity_id,
        "source_identity_verified": attestation.source_identity_verified,
        "source_identity_policy_version": attestation.source_identity_policy_version,
        "source_identity_verification_method": attestation.source_identity_verification_method,
        "repository": acquired.repository,
        "revision": acquired.trusted_record.source_revision,
        "path": acquired.path,
        "source_sha256": assessment["source_sha256"],
        "source_bundle_sha256": acquired.source_bundle_sha256,
        "source_bundle_paths": list(acquired.source_bundle_paths),
        "external_references_resolved": assessment["external_references_resolved"],
        "title": assessment["title"],
        "version": assessment["version"],
        "dialect": assessment["dialect"],
        "contract_family": assessment["contract_family"],
        "operation_count": assessment["operation_count"],
        "blocker_codes": assessment["blocker_codes"],
        "warning_codes": assessment["warning_codes"],
        "discovery_quality_passed": assessment["discovery_quality_passed"],
        "binding_generation_ready": assessment["binding_generation_ready"],
        "production_allowed": False,
        "runtime_connector_approved": False,
        "provider_credentials_present": False,
        "provider_network_proof": False,
        "provider_sandbox_proven": False,
    }


def main() -> int:
    evidence = asyncio.run(qualify_reviewed_camara_qod_public_source())
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return 0 if evidence["discovery_quality_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["qualify_reviewed_camara_qod_public_source"]
