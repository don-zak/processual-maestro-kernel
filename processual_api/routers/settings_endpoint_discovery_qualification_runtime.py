"""Server-side discovery qualification for Enterprise endpoint bindings."""

from __future__ import annotations

import hmac
import re
from typing import Any

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user
from processual_api.integrations.endpoint_binding_provenance import (
    EndpointBindingProvenance,
    EndpointBindingProvenanceError,
    provenance_matches_binding,
    qualify_binding_from_discovery,
)
from processual_api.integrations.endpoint_discovery_quality import (
    EndpointDiscoveryError,
    assess_endpoint_discovery,
    canonical_api_description_sha256,
)
from processual_api.integrations.endpoint_source_attestation import (
    attest_endpoint_source_identity,
)

from . import settings as settings_module
from . import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from . import settings_enterprise_integration_runtime as enterprise_runtime

DISCOVERY_PROVENANCE_STORAGE_KEY = "enterprise_endpoint_discovery_provenance_v1"
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EndpointDiscoveryQualificationRequest(BaseModel):
    api_description: dict[str, Any]
    contract_family: str = Field(min_length=1, max_length=80)
    source_reference: str = Field(min_length=1, max_length=1000)
    source_kind: str = Field(default="unverified", min_length=1, max_length=40)
    source_revision: str = Field(default="", max_length=128)
    # Deprecated transition claims. They remain parseable so older clients get a
    # fail-closed qualification result rather than a schema error, but they are
    # not used to establish source or external-reference authority.
    release_pinned: bool | None = None
    external_references_resolved: bool | None = None
    operation_id: str = Field(min_length=1, max_length=300)


def _require_enterprise(current_user: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    user_id, raw, capability = enterprise_runtime._client_enterprise_capability(
        current_user=current_user
    )
    enterprise_runtime._require_enterprise_entitlement(capability)
    return user_id, raw


def _stored_provenance(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get(DISCOVERY_PROVENANCE_STORAGE_KEY, [])
    return [dict(item) for item in items if isinstance(item, dict)]


def _find_provenance(
    raw: dict[str, Any],
    binding_id: str,
) -> EndpointBindingProvenance | None:
    for item in reversed(_stored_provenance(raw)):
        if str(item.get("binding_id") or "") != binding_id:
            continue
        try:
            return EndpointBindingProvenance(**{
                key: value for key, value in item.items() if key != "binding_id"
            })
        except ValueError:
            return None
    return None


def _verified_source_pin(
    body: EndpointDiscoveryQualificationRequest,
) -> tuple[str, str, bool]:
    source_kind = body.source_kind.strip().lower()
    source_revision = body.source_revision.strip().lower()
    source_reference = body.source_reference.strip().lower()
    document_sha256 = canonical_api_description_sha256(body.api_description)

    if source_kind == "artifact_sha256":
        if source_revision.startswith("sha256:"):
            source_revision = source_revision.removeprefix("sha256:")
        verified = bool(
            _SHA256.fullmatch(source_revision)
            and hmac.compare_digest(source_revision, document_sha256)
        )
        return source_kind, source_revision, verified

    if source_kind == "git_commit":
        verified = bool(
            _GIT_COMMIT.fullmatch(source_revision)
            and source_revision in source_reference
        )
        return source_kind, source_revision, verified

    return source_kind, source_revision, False


def _safe_projection(
    binding_id: str,
    provenance: EndpointBindingProvenance,
    *,
    matches_binding: bool,
) -> dict[str, Any]:
    return {
        "binding_id": binding_id,
        **provenance.model_dump(),
        "qualification_state": "qualified" if matches_binding else "drifted",
        "provenance_matches_binding": matches_binding,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.get(
    "/enterprise-integration/endpoint-bindings/{binding_id}/discovery-qualification",
    response_model=dict,
)
async def get_endpoint_discovery_qualification(
    binding_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _, raw = _require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    provenance = _find_provenance(raw, binding_id)
    if provenance is None:
        return {
            "binding_id": binding_id,
            "qualification_state": "not_qualified",
            "provenance_matches_binding": False,
            "source_identity_verified": False,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "raw_secret_visible": False,
        }
    return _safe_projection(
        binding_id,
        provenance,
        matches_binding=provenance_matches_binding(spec, provenance),
    )


@settings_module.router.post(
    "/enterprise-integration/endpoint-bindings/{binding_id}/discovery-qualification",
    response_model=dict,
)
async def qualify_endpoint_binding_discovery(
    binding_id: str,
    body: EndpointDiscoveryQualificationRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    user_id, raw = _require_enterprise(current_user)
    spec = binding_runtime._find_binding(raw, binding_id)
    source_kind, source_revision, source_pin_verified = _verified_source_pin(body)
    try:
        # External references are deliberately fail-closed here. A caller must
        # submit a self-contained/bundled description before qualification;
        # the deprecated boolean claim cannot turn an unresolved $ref into
        # verified evidence.
        assessment = assess_endpoint_discovery(
            body.api_description,
            contract_family=body.contract_family,
            source_reference=body.source_reference,
            release_pinned=source_pin_verified,
            external_references_resolved=False,
        )
        source_attestation = attest_endpoint_source_identity(
            source_reference=body.source_reference,
            source_kind=source_kind,
            source_revision=source_revision,
            source_sha256=assessment["source_sha256"],
            contract_family=assessment["contract_family"],
        )
        assessment.update(
            {
                "source_kind": source_kind,
                "source_revision": source_revision,
                "source_pin_verified": source_pin_verified,
                "source_identity_id": source_attestation.source_identity_id,
                "source_identity_verified": source_attestation.source_identity_verified,
                "source_identity_policy_version": (
                    source_attestation.source_identity_policy_version
                ),
                "source_identity_verification_method": (
                    source_attestation.source_identity_verification_method
                ),
            }
        )
        provenance = qualify_binding_from_discovery(
            spec,
            assessment,
            operation_id=body.operation_id,
        )
    except (
        EndpointDiscoveryError,
        EndpointBindingProvenanceError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    items = [
        item
        for item in _stored_provenance(raw)
        if str(item.get("binding_id") or "") != binding_id
    ]
    items.append({"binding_id": binding_id, **provenance.model_dump()})
    raw[DISCOVERY_PROVENANCE_STORAGE_KEY] = items[-100:]
    settings_module._save_raw(user_id, raw)

    return {
        "status": "discovery_qualified",
        "persisted": True,
        "assessment": {
            "source_reference": assessment["source_reference"],
            "source_sha256": assessment["source_sha256"],
            "source_kind": source_kind,
            "source_revision": source_revision,
            "source_pin_verified": source_pin_verified,
            "source_identity_id": source_attestation.source_identity_id,
            "source_identity_verified": source_attestation.source_identity_verified,
            "source_identity_policy_version": (
                source_attestation.source_identity_policy_version
            ),
            "source_identity_verification_method": (
                source_attestation.source_identity_verification_method
            ),
            "title": assessment["title"],
            "version": assessment["version"],
            "dialect": assessment["dialect"],
            "contract_family": assessment["contract_family"],
            "operation_count": assessment["operation_count"],
            "defined_security_schemes": assessment["defined_security_schemes"],
            "undefined_security_schemes": assessment["undefined_security_schemes"],
            "external_reference_count": assessment["external_reference_count"],
            "external_references_resolved": assessment["external_references_resolved"],
            "blocker_codes": assessment["blocker_codes"],
            "warning_codes": assessment["warning_codes"],
            "discovery_quality_passed": assessment["discovery_quality_passed"],
            "binding_generation_ready": assessment["binding_generation_ready"],
        },
        "provenance": _safe_projection(
            binding_id,
            provenance,
            matches_binding=True,
        ),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "DISCOVERY_PROVENANCE_STORAGE_KEY",
    "EndpointDiscoveryQualificationRequest",
    "get_endpoint_discovery_qualification",
    "qualify_endpoint_binding_discovery",
]
