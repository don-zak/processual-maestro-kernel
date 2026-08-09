from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_SPECS,
    get_plan_fulfillment_spec,
    normalize_plan_code,
)

PLAN_CAPABILITY_MATRIX_VERSION: Final = "2026-08-plan-capabilities-v2"


class CapabilityStatus(StrEnum):
    READY = "ready"
    SANDBOX_ONLY = "sandbox_only"
    INTERNAL_ONLY = "internal_only"
    NOT_EXPOSED = "not_exposed"


@dataclass(frozen=True, slots=True)
class ToolCapability:
    capability_code: str
    entitlement_code: str
    status: CapabilityStatus
    execution_surface: str
    customer_executable: bool
    production_allowed: bool
    notes: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True, slots=True)
class ExecutionCapabilityPolicy:
    method: str
    path: str
    capability_code: str
    quota_metric: str
    quota_cost: int
    production_required: bool = False


_TOOL_CAPABILITIES = {
    "maestro_execution": ToolCapability(
        capability_code="maestro_execution",
        entitlement_code="maestro_execution",
        status=CapabilityStatus.READY,
        execution_surface="/workflows and /workflows/llm-orchestration",
        customer_executable=True,
        production_allowed=True,
        notes="Interactive governed workflow execution is mounted and authenticated.",
    ),
    "byok_provider_connection": ToolCapability(
        capability_code="byok_provider_connection",
        entitlement_code="byok_provider_connection",
        status=CapabilityStatus.READY,
        execution_surface="/settings/provider-connection/test",
        customer_executable=True,
        production_allowed=True,
        notes="Customer-owned provider credentials can be validated through the provider runtime.",
    ),
    "standard_support": ToolCapability(
        capability_code="standard_support",
        entitlement_code="standard_support",
        status=CapabilityStatus.NOT_EXPOSED,
        execution_surface="support_policy",
        customer_executable=False,
        production_allowed=False,
        notes="Support level is a service entitlement, not an executable API tool.",
    ),
    "business_support": ToolCapability(
        capability_code="business_support",
        entitlement_code="business_support",
        status=CapabilityStatus.NOT_EXPOSED,
        execution_surface="support_policy",
        customer_executable=False,
        production_allowed=False,
        notes="Support level is a service entitlement, not an executable API tool.",
    ),
    "enterprise_governance": ToolCapability(
        capability_code="enterprise_governance",
        entitlement_code="enterprise_governance",
        status=CapabilityStatus.READY,
        execution_surface="/cgt/govern and governance reporting surfaces",
        customer_executable=True,
        production_allowed=True,
        notes="Governance evaluation, reporting, and repair surfaces are implemented.",
    ),
    "advanced_integration": ToolCapability(
        capability_code="advanced_integration",
        entitlement_code="advanced_integration",
        status=CapabilityStatus.SANDBOX_ONLY,
        execution_surface="/settings/enterprise-integration",
        customer_executable=True,
        production_allowed=False,
        notes=(
            "Customer-specific qualification and supervised review are available; "
            "external production runtime connectors remain disabled."
        ),
    ),
    "academic_use": ToolCapability(
        capability_code="academic_use",
        entitlement_code="academic_use",
        status=CapabilityStatus.NOT_EXPOSED,
        execution_surface="usage_policy",
        customer_executable=False,
        production_allowed=False,
        notes="Academic-use classification is contractual metadata and has no distinct runtime tool gate yet.",
    ),
}

TOOL_CAPABILITIES: Final = MappingProxyType(_TOOL_CAPABILITIES)

_EXECUTION_POLICIES = {
    ("POST", "/cgt/govern"): ExecutionCapabilityPolicy(
        method="POST",
        path="/cgt/govern",
        capability_code="maestro_execution",
        quota_metric="credits",
        quota_cost=1,
    ),
}

EXECUTION_CAPABILITY_POLICIES: Final = MappingProxyType(_EXECUTION_POLICIES)


def _normalize_path(path: str) -> str:
    normalized = str(path or "").strip() or "/"
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized


def execution_policy_for_request(
    method: str,
    path: str,
) -> ExecutionCapabilityPolicy | None:
    return EXECUTION_CAPABILITY_POLICIES.get(
        (str(method or "").upper(), _normalize_path(path))
    )


def required_execution_capability(method: str, path: str) -> str | None:
    policy = execution_policy_for_request(method, path)
    return None if policy is None else policy.capability_code


def execution_quota_cost(method: str, path: str) -> tuple[str, int] | None:
    policy = execution_policy_for_request(method, path)
    if policy is None:
        return None
    return policy.quota_metric, policy.quota_cost


def capabilities_for_plan(plan_code: str | None) -> tuple[ToolCapability, ...]:
    spec = get_plan_fulfillment_spec(plan_code)
    capabilities: list[ToolCapability] = []
    for entitlement_code in spec.entitlement_codes:
        capability = TOOL_CAPABILITIES.get(entitlement_code)
        if capability is None:
            raise KeyError(
                f"missing tool capability mapping for entitlement: {entitlement_code}"
            )
        capabilities.append(capability)
    return tuple(capabilities)


def plan_can_execute(
    plan_code: str | None,
    capability_code: str,
    *,
    require_production: bool = False,
) -> bool:
    normalized_capability = str(capability_code or "").strip().lower()
    if not normalized_capability:
        return False
    try:
        capabilities = capabilities_for_plan(plan_code)
    except KeyError:
        return False

    for capability in capabilities:
        if capability.capability_code != normalized_capability:
            continue
        if not capability.customer_executable:
            return False
        if require_production and not capability.production_allowed:
            return False
        return capability.status in {
            CapabilityStatus.READY,
            CapabilityStatus.SANDBOX_ONLY,
        }
    return False


def plan_capability_payload(plan_code: str | None) -> dict[str, object]:
    canonical = normalize_plan_code(plan_code)
    capabilities = capabilities_for_plan(canonical)
    return {
        "matrix_version": PLAN_CAPABILITY_MATRIX_VERSION,
        "plan_code": canonical,
        "capabilities": [capability.to_dict() for capability in capabilities],
        "execution_policies": [
            asdict(policy) for policy in EXECUTION_CAPABILITY_POLICIES.values()
        ],
        "production_advanced_integration_allowed": plan_can_execute(
            canonical,
            "advanced_integration",
            require_production=True,
        ),
    }


def validate_plan_capability_matrix() -> None:
    entitlement_codes = {
        entitlement
        for spec in PLAN_FULFILLMENT_SPECS.values()
        for entitlement in spec.entitlement_codes
    }
    missing = entitlement_codes - set(TOOL_CAPABILITIES)
    if missing:
        raise ValueError(
            "plan capability matrix is missing entitlement mappings: "
            + ", ".join(sorted(missing))
        )

    for plan_code in PLAN_FULFILLMENT_SPECS:
        capabilities_for_plan(plan_code)

    for policy in EXECUTION_CAPABILITY_POLICIES.values():
        if policy.capability_code not in TOOL_CAPABILITIES:
            raise ValueError(
                f"execution policy references unknown capability: {policy.capability_code}"
            )
        if policy.quota_metric != "credits":
            raise ValueError("execution quota metric must remain canonical credits")
        if policy.quota_cost <= 0:
            raise ValueError("execution quota cost must be positive")

    advanced = TOOL_CAPABILITIES["advanced_integration"]
    if advanced.production_allowed or advanced.status is not CapabilityStatus.SANDBOX_ONLY:
        raise ValueError("advanced integration must remain sandbox-only")


validate_plan_capability_matrix()


__all__ = [
    "CapabilityStatus",
    "EXECUTION_CAPABILITY_POLICIES",
    "ExecutionCapabilityPolicy",
    "PLAN_CAPABILITY_MATRIX_VERSION",
    "TOOL_CAPABILITIES",
    "ToolCapability",
    "capabilities_for_plan",
    "execution_policy_for_request",
    "execution_quota_cost",
    "plan_can_execute",
    "plan_capability_payload",
    "required_execution_capability",
    "validate_plan_capability_matrix",
]
