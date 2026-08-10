from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.billing.plan_capability_matrix import (
    CapabilityStatus,
    TOOL_CAPABILITIES,
)


class ApiVisibility(StrEnum):
    PUBLIC = "public"
    CUSTOMER = "customer"
    ADMIN = "admin"
    INTERNAL = "internal"


class ApiReadiness(StrEnum):
    PRODUCTION_READY = "production_ready"
    SANDBOX_ONLY = "sandbox_only"
    INTERNAL_ONLY = "internal_only"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ApiSurfacePolicy:
    surface_id: str
    path_prefix: str
    visibility: ApiVisibility
    readiness: ApiReadiness
    auth_required: bool
    audit_required: bool
    external_dependency: str | None = None
    capability_code: str | None = None
    production_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["visibility"] = self.visibility.value
        payload["readiness"] = self.readiness.value
        return payload


_API_SURFACE_POLICIES = {
    "health": ApiSurfacePolicy(
        surface_id="health",
        path_prefix="/health",
        visibility=ApiVisibility.PUBLIC,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=False,
        audit_required=False,
        production_allowed=True,
    ),
    "workflows": ApiSurfacePolicy(
        surface_id="workflows",
        path_prefix="/workflows",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        capability_code="maestro_execution",
        production_allowed=True,
    ),
    "cgt": ApiSurfacePolicy(
        surface_id="cgt",
        path_prefix="/cgt",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        capability_code="maestro_execution",
        production_allowed=True,
    ),
    "governance": ApiSurfacePolicy(
        surface_id="governance",
        path_prefix="/governance",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        capability_code="enterprise_governance",
        production_allowed=True,
    ),
    "reports": ApiSurfacePolicy(
        surface_id="reports",
        path_prefix="/reports",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        production_allowed=True,
    ),
    "provider_connection": ApiSurfacePolicy(
        surface_id="provider_connection",
        path_prefix="/settings/provider-connection",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        external_dependency="customer_provider",
        capability_code="byok_provider_connection",
        production_allowed=True,
    ),
    "advanced_integration": ApiSurfacePolicy(
        surface_id="advanced_integration",
        path_prefix="/settings/enterprise-integration",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.SANDBOX_ONLY,
        auth_required=True,
        audit_required=True,
        external_dependency="qualified_external_connector",
        capability_code="advanced_integration",
        production_allowed=False,
    ),
    "admin_marketplace": ApiSurfacePolicy(
        surface_id="admin_marketplace",
        path_prefix="/admin-marketplace",
        visibility=ApiVisibility.ADMIN,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        external_dependency="commercial_persistence",
        production_allowed=True,
    ),
    "integration_readiness_admin": ApiSurfacePolicy(
        surface_id="integration_readiness_admin",
        path_prefix="/settings/admin/integration-readiness-tracking",
        visibility=ApiVisibility.ADMIN,
        readiness=ApiReadiness.PRODUCTION_READY,
        auth_required=True,
        audit_required=True,
        production_allowed=True,
    ),
    "durable_execution": ApiSurfacePolicy(
        surface_id="durable_execution",
        path_prefix="/internal/execution",
        visibility=ApiVisibility.INTERNAL,
        readiness=ApiReadiness.INTERNAL_ONLY,
        auth_required=True,
        audit_required=True,
        capability_code="durable_execution_internal",
        production_allowed=False,
    ),
    "topup_public_purchase": ApiSurfacePolicy(
        surface_id="topup_public_purchase",
        path_prefix="/billing/topups/purchase",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.DISABLED,
        auth_required=True,
        audit_required=True,
        external_dependency="payment_channel_readiness",
        production_allowed=False,
    ),
}

API_SURFACE_POLICIES: Final = MappingProxyType(_API_SURFACE_POLICIES)


def _normalize_path(path: str) -> str:
    value = str(path or "").strip() or "/"
    if value != "/":
        value = value.rstrip("/")
    return value


def readiness_for_path(path: str) -> ApiSurfacePolicy | None:
    normalized = _normalize_path(path)
    matches = [
        policy
        for policy in API_SURFACE_POLICIES.values()
        if normalized == policy.path_prefix
        or normalized.startswith(policy.path_prefix.rstrip("/") + "/")
    ]
    if not matches:
        return None
    return max(matches, key=lambda policy: len(policy.path_prefix))


def production_surface_allowed(path: str) -> bool:
    policy = readiness_for_path(path)
    return bool(
        policy is not None
        and policy.production_allowed
        and policy.readiness is ApiReadiness.PRODUCTION_READY
    )


def validate_api_readiness_registry() -> None:
    seen_prefixes: set[str] = set()
    for key, policy in API_SURFACE_POLICIES.items():
        if key != policy.surface_id:
            raise ValueError(f"surface key mismatch: {key}")
        if not policy.path_prefix.startswith("/"):
            raise ValueError(f"surface path must be absolute: {policy.surface_id}")
        if policy.path_prefix in seen_prefixes:
            raise ValueError(f"duplicate surface prefix: {policy.path_prefix}")
        seen_prefixes.add(policy.path_prefix)

        if policy.visibility in {ApiVisibility.CUSTOMER, ApiVisibility.ADMIN, ApiVisibility.INTERNAL}:
            if not policy.auth_required:
                raise ValueError(f"non-public surface must require auth: {policy.surface_id}")

        if policy.readiness is not ApiReadiness.PRODUCTION_READY and policy.production_allowed:
            raise ValueError(
                f"non-ready surface cannot allow production: {policy.surface_id}"
            )

        if policy.capability_code is not None:
            capability = TOOL_CAPABILITIES.get(policy.capability_code)
            if capability is None:
                raise ValueError(
                    f"surface references unknown capability: {policy.capability_code}"
                )
            if policy.production_allowed and not capability.production_allowed:
                raise ValueError(
                    f"surface production policy exceeds capability authority: {policy.surface_id}"
                )

    advanced = API_SURFACE_POLICIES["advanced_integration"]
    if (
        advanced.readiness is not ApiReadiness.SANDBOX_ONLY
        or advanced.production_allowed
        or TOOL_CAPABILITIES["advanced_integration"].status
        is not CapabilityStatus.SANDBOX_ONLY
    ):
        raise ValueError("advanced integration must remain sandbox-only")

    durable = API_SURFACE_POLICIES["durable_execution"]
    if (
        durable.visibility is not ApiVisibility.INTERNAL
        or durable.readiness is not ApiReadiness.INTERNAL_ONLY
        or durable.production_allowed
    ):
        raise ValueError("durable execution must remain internal-only")

    topup = API_SURFACE_POLICIES["topup_public_purchase"]
    if topup.readiness is not ApiReadiness.DISABLED or topup.production_allowed:
        raise ValueError("public top-up purchase must remain disabled until qualified")


validate_api_readiness_registry()


__all__ = [
    "API_SURFACE_POLICIES",
    "ApiReadiness",
    "ApiSurfacePolicy",
    "ApiVisibility",
    "production_surface_allowed",
    "readiness_for_path",
    "validate_api_readiness_registry",
]
