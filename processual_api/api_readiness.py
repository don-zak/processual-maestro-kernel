from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.billing.plan_capability_matrix import (
    TOOL_CAPABILITIES,
    CapabilityStatus,
)


class ApiVisibility(StrEnum):
    PUBLIC = "public"
    CUSTOMER = "customer"
    ADMIN = "admin"
    INTERNAL = "internal"
    MIXED = "mixed"


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


def _sandbox_integration_surface(
    surface_id: str,
    path_prefix: str,
    visibility: ApiVisibility,
) -> ApiSurfacePolicy:
    return ApiSurfacePolicy(
        surface_id=surface_id,
        path_prefix=path_prefix,
        visibility=visibility,
        readiness=ApiReadiness.SANDBOX_ONLY,
        auth_required=True,
        audit_required=True,
        external_dependency="qualified_external_connector",
        capability_code="advanced_integration",
        production_allowed=False,
    )


def _unqualified_mixed_surface(
    surface_id: str,
    path_prefix: str,
) -> ApiSurfacePolicy:
    """Classify optional route families without promoting them."""
    return ApiSurfacePolicy(
        surface_id=surface_id,
        path_prefix=path_prefix,
        visibility=ApiVisibility.MIXED,
        readiness=ApiReadiness.DISABLED,
        auth_required=False,
        audit_required=True,
        production_allowed=False,
    )


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
    "metrics": ApiSurfacePolicy(
        surface_id="metrics",
        path_prefix="/metrics",
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
    "advanced_integration": _sandbox_integration_surface(
        "advanced_integration",
        "/settings/enterprise-integration",
        ApiVisibility.CUSTOMER,
    ),
    "external_connectivity_admin": _sandbox_integration_surface(
        "external_connectivity_admin",
        "/settings/admin/external-connectivity",
        ApiVisibility.ADMIN,
    ),
    "integration_claim_keys_admin": _sandbox_integration_surface(
        "integration_claim_keys_admin",
        "/settings/admin/integration-claim-keys",
        ApiVisibility.ADMIN,
    ),
    "integration_tasks_admin": _sandbox_integration_surface(
        "integration_tasks_admin",
        "/settings/admin/integration-tasks",
        ApiVisibility.ADMIN,
    ),
    "operator_pilot_handoff": _sandbox_integration_surface(
        "operator_pilot_handoff",
        "/settings/admin/operator-pilot-handoff",
        ApiVisibility.ADMIN,
    ),
    "external_connectivity_client": _sandbox_integration_surface(
        "external_connectivity_client",
        "/settings/client/external-connectivity",
        ApiVisibility.CUSTOMER,
    ),
    "integration_claim_keys_client": _sandbox_integration_surface(
        "integration_claim_keys_client",
        "/settings/client/integration-claim-keys",
        ApiVisibility.CUSTOMER,
    ),
    "integration_onboarding_client": _sandbox_integration_surface(
        "integration_onboarding_client",
        "/settings/client/integration-onboarding",
        ApiVisibility.CUSTOMER,
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
    "integration_readiness_operator_package": ApiSurfacePolicy(
        surface_id="integration_readiness_operator_package",
        path_prefix=(
            "/settings/admin/integration-readiness-operator-package"
        ),
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
    "billing_statements_customer": ApiSurfacePolicy(
        surface_id="billing_statements_customer",
        path_prefix="/billing/statements",
        visibility=ApiVisibility.CUSTOMER,
        readiness=ApiReadiness.SANDBOX_ONLY,
        auth_required=True,
        audit_required=True,
        external_dependency="authoritative_usage_and_quota_ledger",
        production_allowed=False,
    ),
    "billing_statements_admin": ApiSurfacePolicy(
        surface_id="billing_statements_admin",
        path_prefix="/billing/admin/statements",
        visibility=ApiVisibility.ADMIN,
        readiness=ApiReadiness.SANDBOX_ONLY,
        auth_required=True,
        audit_required=True,
        external_dependency="authoritative_usage_and_quota_ledger",
        production_allowed=False,
    ),
    "full_install_adapters": _unqualified_mixed_surface(
        "full_install_adapters",
        "/adapters",
    ),
    "full_install_applications": _unqualified_mixed_surface(
        "full_install_applications",
        "/applications",
    ),
    "full_install_auth": _unqualified_mixed_surface(
        "full_install_auth",
        "/auth",
    ),
    "full_install_billing": _unqualified_mixed_surface(
        "full_install_billing",
        "/billing",
    ),
    "full_install_discord": _unqualified_mixed_surface(
        "full_install_discord",
        "/discord",
    ),
    "full_install_settings": _unqualified_mixed_surface(
        "full_install_settings",
        "/settings",
    ),
    "full_install_telemetry": _unqualified_mixed_surface(
        "full_install_telemetry",
        "/telemetry",
    ),
}

API_SURFACE_POLICIES: Final = MappingProxyType(
    _API_SURFACE_POLICIES
)


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
        or normalized.startswith(
            policy.path_prefix.rstrip("/") + "/"
        )
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda policy: len(policy.path_prefix),
    )


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
            raise ValueError(
                f"surface key mismatch: {key}"
            )
        if not policy.path_prefix.startswith("/"):
            raise ValueError(
                "surface path must be absolute: "
                f"{policy.surface_id}"
            )
        if policy.path_prefix in seen_prefixes:
            raise ValueError(
                "duplicate surface prefix: "
                f"{policy.path_prefix}"
            )
        seen_prefixes.add(policy.path_prefix)

        if policy.visibility in {
            ApiVisibility.CUSTOMER,
            ApiVisibility.ADMIN,
            ApiVisibility.INTERNAL,
        } and not policy.auth_required:
            raise ValueError(
                "non-public surface must require auth: "
                f"{policy.surface_id}"
            )

        if (
            policy.readiness is not ApiReadiness.PRODUCTION_READY
            and policy.production_allowed
        ):
            raise ValueError(
                "non-ready surface cannot allow production: "
                f"{policy.surface_id}"
            )

        if policy.capability_code is not None:
            capability = TOOL_CAPABILITIES.get(
                policy.capability_code
            )
            if capability is None:
                raise ValueError(
                    "surface references unknown capability: "
                    f"{policy.capability_code}"
                )
            if (
                policy.production_allowed
                and not capability.production_allowed
            ):
                raise ValueError(
                    "surface production policy exceeds "
                    "capability authority: "
                    f"{policy.surface_id}"
                )

    sandbox_surfaces = (
        "advanced_integration",
        "external_connectivity_admin",
        "integration_claim_keys_admin",
        "integration_tasks_admin",
        "operator_pilot_handoff",
        "external_connectivity_client",
        "integration_claim_keys_client",
        "integration_onboarding_client",
    )
    for surface_id in sandbox_surfaces:
        policy = API_SURFACE_POLICIES[surface_id]
        if (
            policy.readiness is not ApiReadiness.SANDBOX_ONLY
            or policy.production_allowed
            or policy.capability_code != "advanced_integration"
            or TOOL_CAPABILITIES["advanced_integration"].status
            is not CapabilityStatus.SANDBOX_ONLY
        ):
            raise ValueError(
                "advanced integration surface must remain "
                f"sandbox-only: {surface_id}"
            )

    for surface_id in (
        "billing_statements_customer",
        "billing_statements_admin",
    ):
        policy = API_SURFACE_POLICIES[surface_id]
        if (
            policy.readiness is not ApiReadiness.SANDBOX_ONLY
            or policy.production_allowed
            or not policy.auth_required
            or not policy.audit_required
        ):
            raise ValueError(
                "billing statements must remain explicitly "
                f"qualified before production: {surface_id}"
            )

    unqualified_full_install_surfaces = (
        "full_install_adapters",
        "full_install_applications",
        "full_install_auth",
        "full_install_billing",
        "full_install_discord",
        "full_install_settings",
        "full_install_telemetry",
    )
    for surface_id in unqualified_full_install_surfaces:
        policy = API_SURFACE_POLICIES[surface_id]
        if (
            policy.visibility is not ApiVisibility.MIXED
            or policy.readiness is not ApiReadiness.DISABLED
            or policy.production_allowed
        ):
            raise ValueError(
                "unqualified full-install surface must "
                f"remain disabled: {surface_id}"
            )

    durable = API_SURFACE_POLICIES["durable_execution"]
    if (
        durable.visibility is not ApiVisibility.INTERNAL
        or durable.readiness is not ApiReadiness.INTERNAL_ONLY
        or durable.production_allowed
    ):
        raise ValueError(
            "durable execution must remain internal-only"
        )

    topup = API_SURFACE_POLICIES["topup_public_purchase"]
    if (
        topup.readiness is not ApiReadiness.DISABLED
        or topup.production_allowed
    ):
        raise ValueError(
            "public top-up purchase must remain disabled "
            "until qualified"
        )


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
