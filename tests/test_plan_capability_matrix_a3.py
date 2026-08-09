from __future__ import annotations

import pytest

from processual_api.billing.plan_capability_matrix import (
    CapabilityStatus,
    TOOL_CAPABILITIES,
    capabilities_for_plan,
    plan_can_execute,
    plan_capability_payload,
    validate_plan_capability_matrix,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS


@pytest.mark.parametrize("plan_code", tuple(PLAN_FULFILLMENT_SPECS))
def test_every_authoritative_plan_has_complete_capability_mapping(plan_code: str) -> None:
    spec = PLAN_FULFILLMENT_SPECS[plan_code]
    capabilities = capabilities_for_plan(plan_code)

    assert tuple(item.entitlement_code for item in capabilities) == spec.entitlement_codes
    assert all(item.capability_code in TOOL_CAPABILITIES for item in capabilities)


def test_matrix_validation_passes_for_current_catalog() -> None:
    validate_plan_capability_matrix()


def test_customer_execution_capabilities_are_explicit() -> None:
    assert plan_can_execute("starter", "maestro_execution") is True
    assert plan_can_execute("starter", "byok_provider_connection") is True
    assert plan_can_execute("starter", "enterprise_governance") is False
    assert plan_can_execute("academic", "academic_use") is False


def test_enterprise_governance_requires_enterprise_entitlement() -> None:
    assert plan_can_execute("business", "enterprise_governance") is False
    assert plan_can_execute("enterprise_pilot", "enterprise_governance") is True
    assert plan_can_execute("enterprise_core", "enterprise_governance") is True


def test_advanced_integration_is_sandbox_only_and_never_production() -> None:
    capability = TOOL_CAPABILITIES["advanced_integration"]

    assert capability.status is CapabilityStatus.SANDBOX_ONLY
    assert capability.customer_executable is True
    assert capability.production_allowed is False
    assert plan_can_execute("enterprise_scale", "advanced_integration") is True
    assert (
        plan_can_execute(
            "enterprise_scale",
            "advanced_integration",
            require_production=True,
        )
        is False
    )
    assert (
        plan_can_execute(
            "enterprise_strategic",
            "advanced_integration",
            require_production=True,
        )
        is False
    )


def test_unknown_plan_or_capability_fails_closed() -> None:
    assert plan_can_execute("not_a_plan", "maestro_execution") is False
    assert plan_can_execute("starter", "not_a_capability") is False


def test_payload_keeps_production_integration_boundary_closed() -> None:
    payload = plan_capability_payload("enterprise_scale")

    assert payload["plan_code"] == "enterprise_scale"
    assert payload["production_advanced_integration_allowed"] is False
    advanced = next(
        item
        for item in payload["capabilities"]
        if item["capability_code"] == "advanced_integration"
    )
    assert advanced["status"] == "sandbox_only"
    assert advanced["production_allowed"] is False
