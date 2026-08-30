from processual_api.admin_marketplace.commercial_plan_projection import (
    COMMERCIAL_PLAN_PROJECTION_VERSION,
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.admin_marketplace.subscription_quota_profiles import (
    validate_quota_profile,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    PLAN_FULFILLMENT_SPECS,
    QUOTA_METRIC_CODE,
)


def test_plan_projection_contains_only_canonical_plan_codes() -> None:
    projections = build_commercial_plan_projections()
    plan_codes = {item.plan_code for item in projections}

    assert plan_codes == set(PLAN_FULFILLMENT_SPECS)
    assert plan_codes.isdisjoint({"pilot_starter", "enterprise", "enterprise_integration"})


def test_plan_projection_is_versioned_and_does_not_shadow_quota_values() -> None:
    for projection in build_commercial_plan_projections():
        spec = PLAN_FULFILLMENT_SPECS[projection.plan_code]
        assert projection.monthly_unit_allowance == spec.monthly_unit_allowance
        assert projection.entitlement_codes == spec.entitlement_codes
        assert projection.entitlement_profile_ref.endswith(PLAN_FULFILLMENT_CATALOG_VERSION)
        assert projection.quota_profile_ref.endswith(PLAN_FULFILLMENT_CATALOG_VERSION)
        assert projection.metadata["projection_version"] == COMMERCIAL_PLAN_PROJECTION_VERSION
        assert projection.metadata["commercial_authority"] == "commercial_catalog_contracts"


def test_projected_quota_profiles_validate_and_match_maestro_units() -> None:
    projections = {item.quota_profile_ref: item for item in build_commercial_plan_projections()}
    profiles = build_subscription_quota_profiles()

    assert len(profiles) == len(projections)
    for raw_profile in profiles:
        profile = validate_quota_profile(raw_profile)
        projection = projections[profile.profile_ref]
        assert profile.period_days == 30
        assert len(profile.metrics) == 1
        metric = profile.metrics[0]
        assert metric.metric_code == QUOTA_METRIC_CODE
        assert metric.limit_units == projection.monthly_unit_allowance
