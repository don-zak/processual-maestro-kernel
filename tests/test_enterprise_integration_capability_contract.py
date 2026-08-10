from __future__ import annotations

from processual_api.billing.usage_pricing import (
    ENTERPRISE_INTEGRATION_PLANS,
    allows_enterprise_integration,
    enterprise_integration_capability,
)


def test_enterprise_integration_capability_enables_authoritative_enterprise_plans() -> None:
    for plan_id in ENTERPRISE_INTEGRATION_PLANS:
        capability = enterprise_integration_capability(plan_id)

        assert capability["enabled"] is True
        assert capability["status"] == "available"
        assert capability["legacy_compatibility"] is False
        assert allows_enterprise_integration(plan_id) is True


def test_enterprise_integration_capability_preserves_public_aliases() -> None:
    for plan_id in ("enterprise", "enterprise_integration"):
        capability = enterprise_integration_capability(plan_id)

        assert capability["enabled"] is True
        assert capability["normalized_plan_id"] == plan_id
        assert capability["canonical_plan_id"] == "enterprise_pilot"
        assert capability["legacy_compatibility"] is False


def test_enterprise_custom_remains_eligible_without_catalog_quota() -> None:
    capability = enterprise_integration_capability("enterprise_custom")

    assert capability["enabled"] is True
    assert capability["normalized_plan_id"] == "enterprise_custom"
    assert capability["canonical_plan_id"] == "enterprise_custom"
    assert capability["legacy_compatibility"] is False


def test_enterprise_integration_capability_preserves_legacy_private_plan() -> None:
    capability = enterprise_integration_capability("enterprise_private")

    assert capability == {
        "enabled": True,
        "status": "available",
        "plan_id": "enterprise_private",
        "normalized_plan_id": "enterprise_private",
        "canonical_plan_id": "enterprise_private",
        "legacy_compatibility": True,
        "eligible_plans": sorted(ENTERPRISE_INTEGRATION_PLANS),
    }
    assert allows_enterprise_integration("enterprise_private") is True


def test_enterprise_integration_capability_locks_non_enterprise_plans() -> None:
    for plan_id in (None, "", "academic", "starter", "business"):
        capability = enterprise_integration_capability(plan_id)

        assert capability["enabled"] is False
        assert capability["status"] == "locked"
        assert capability["legacy_compatibility"] is False
        assert allows_enterprise_integration(plan_id) is False


def test_enterprise_integration_capability_normalizes_human_entered_plan_ids() -> None:
    capability = enterprise_integration_capability(" Enterprise Integration ")

    assert capability["enabled"] is True
    assert capability["plan_id"] == "enterprise_integration"
    assert capability["normalized_plan_id"] == "enterprise_integration"
    assert capability["canonical_plan_id"] == "enterprise_pilot"
