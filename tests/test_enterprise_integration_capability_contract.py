from __future__ import annotations

from processual_api.billing.usage_pricing import (
    ENTERPRISE_INTEGRATION_PLANS,
    ENTERPRISE_INTEGRATION_QUALIFICATION_PLANS,
    allows_enterprise_integration,
    enterprise_integration_capability,
)


def test_advanced_integration_execution_remains_strictly_entitled() -> None:
    assert ENTERPRISE_INTEGRATION_PLANS == frozenset(
        {
            "enterprise_integration_starter",
            "enterprise_scale",
            "enterprise_strategic",
        }
    )
    for plan_id in ENTERPRISE_INTEGRATION_PLANS:
        assert allows_enterprise_integration(plan_id) is True


def test_enterprise_governance_tiers_can_qualify_without_execution_promotion() -> None:
    assert "enterprise_pilot" in ENTERPRISE_INTEGRATION_QUALIFICATION_PLANS
    assert "enterprise_core" in ENTERPRISE_INTEGRATION_QUALIFICATION_PLANS

    for plan_id in ("enterprise_pilot", "enterprise_core"):
        capability = enterprise_integration_capability(plan_id)
        assert capability["enabled"] is True
        assert capability["status"] == "available"
        assert capability["advanced_integration_enabled"] is False
        assert capability["production_allowed"] is False
        assert allows_enterprise_integration(plan_id) is False


def test_public_enterprise_aliases_preserve_qualification_without_execution_promotion() -> None:
    for plan_id in ("enterprise", "enterprise_integration"):
        capability = enterprise_integration_capability(plan_id)
        assert capability["enabled"] is True
        assert capability["status"] == "available"
        assert capability["normalized_plan_id"] == plan_id
        assert capability["canonical_plan_id"] == "enterprise_pilot"
        assert capability["advanced_integration_enabled"] is False
        assert capability["production_allowed"] is False
        assert allows_enterprise_integration(plan_id) is False


def test_enterprise_custom_requires_explicit_catalog_qualification() -> None:
    capability = enterprise_integration_capability("enterprise_custom")
    assert capability["enabled"] is False
    assert capability["status"] == "locked"
    assert capability["normalized_plan_id"] == "enterprise_custom"
    assert capability["canonical_plan_id"] == "enterprise_custom"
    assert capability["legacy_compatibility"] is False
    assert capability["advanced_integration_enabled"] is False
    assert allows_enterprise_integration("enterprise_custom") is False


def test_enterprise_private_remains_legacy_compatible() -> None:
    capability = enterprise_integration_capability("enterprise_private")
    assert capability["enabled"] is True
    assert capability["status"] == "available"
    assert capability["legacy_compatibility"] is True
    assert capability["advanced_integration_enabled"] is True
    assert capability["production_allowed"] is False
    assert allows_enterprise_integration("enterprise_private") is True


def test_non_enterprise_plans_remain_locked_from_qualification() -> None:
    for plan_id in (None, "", "academic", "starter", "business"):
        capability = enterprise_integration_capability(plan_id)
        assert capability["enabled"] is False
        assert capability["status"] == "locked"
        assert capability["legacy_compatibility"] is False
        assert capability["advanced_integration_enabled"] is False
        assert allows_enterprise_integration(plan_id) is False


def test_human_entered_enterprise_alias_normalizes_for_qualification_only() -> None:
    capability = enterprise_integration_capability(" Enterprise Integration ")
    assert capability["enabled"] is True
    assert capability["status"] == "available"
    assert capability["plan_id"] == "enterprise_integration"
    assert capability["normalized_plan_id"] == "enterprise_integration"
    assert capability["canonical_plan_id"] == "enterprise_pilot"
    assert capability["advanced_integration_enabled"] is False
    assert allows_enterprise_integration(" Enterprise Integration ") is False
