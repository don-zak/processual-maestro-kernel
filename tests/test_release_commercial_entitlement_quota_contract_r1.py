from __future__ import annotations

import json
from pathlib import Path

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS
from processual_api.billing.public_plan_journey import public_plan_journey_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_plan_projection_matches_entitlements_and_quota() -> None:
    projections = {item.plan_code: item for item in build_commercial_plan_projections()}
    profiles = {item.profile_ref: item for item in build_subscription_quota_profiles()}

    assert set(projections) == set(PLAN_FULFILLMENT_SPECS)
    for plan_code, spec in PLAN_FULFILLMENT_SPECS.items():
        projection = projections[plan_code]
        assert projection.monthly_unit_allowance == spec.monthly_unit_allowance
        assert projection.entitlement_codes == spec.entitlement_codes
        quota_profile = profiles[projection.quota_profile_ref]
        assert len(quota_profile.metrics) == 1
        assert quota_profile.metrics[0].limit_units == spec.monthly_unit_allowance
        assert quota_profile.metrics[0].metric_code == "maestro_unit"


def test_public_plan_journey_never_claims_unbound_assessment_quota() -> None:
    catalog = public_plan_journey_catalog()
    plans = {item["plan_id"]: item for item in catalog["plans"]}

    direct_mapping = {
        "academic_individual": "academic",
        "starter": "starter",
        "business": "business",
        "enterprise_pilot": "enterprise_pilot",
    }
    for public_plan_id, fulfillment_plan_id in direct_mapping.items():
        plan = plans[public_plan_id]
        assert plan["requires_assessment"] is False
        assert plan["registration_available"] is True
        assert plan["included_quota_units"] == PLAN_FULFILLMENT_SPECS[
            fulfillment_plan_id
        ].monthly_unit_allowance

    for plan in plans.values():
        if plan["requires_assessment"]:
            assert plan["registration_available"] is False
            assert plan["registration_path"] is None
            assert plan["included_quota_units"] is None


def test_registration_activation_and_usage_are_bound_to_plan_authority() -> None:
    registration = (ROOT / "processual_api/auth/registration_service.py").read_text()
    activation = (
        ROOT / "processual_api/admin_marketplace/subscription_activation_service.py"
    ).read_text()
    usage = (
        ROOT / "processual_api/admin_marketplace/subscription_quota_usage.py"
    ).read_text()

    assert "resolve_direct_registration_plan" in registration
    assert "validate_registration_plan_mode" in registration
    assert "selected_plan_id=selected_plan_id" in registration
    assert "billing_period=billing_period" in registration

    assert "plan.entitlement_profile_ref" in activation
    assert "plan.quota_profile_ref" in activation
    assert "bootstrap_subscription_runtime_in_unit" in activation
    assert "authoritative_quota_profile_required" in activation

    assert 'subscription.status != "active"' in usage
    assert "runtime_allows_usage" in usage
    assert "command.units > cycle.available_units" in usage
    assert "degraded grace usage cap is exhausted" in usage
    assert "idempotency_key_hash" in usage


def test_admin_workspace_exposes_readiness_and_usage_without_becoming_authority() -> None:
    html = (ROOT / "processual_api/static/admin.html").read_text()

    for surface in (
        "Admin Home",
        "Admin Market",
        "Usage Monitor",
        "Program Progress",
        "System Health",
        "System Settings",
        "Supervisor Operations Center",
        "Program &amp; Supervision Readiness",
    ):
        assert surface in html

    assert "Backend enforcement remains authoritative" in html
    assert "no raw keys or provider secrets" in html


def test_infisical_manifest_is_value_free_and_fail_closed() -> None:
    manifest = json.loads(
        (ROOT / "config/infisical/production-secret-manifest.json").read_text()
    )

    assert manifest["environment"] == "production"
    assert manifest["delivery"]["preferred_ci_authentication"] == (
        "github_oidc_machine_identity"
    )
    assert manifest["delivery"]["long_lived_token_in_repository_allowed"] is False
    assert manifest["delivery"]["secret_values_in_repository_allowed"] is False
    assert manifest["delivery"]["runtime_injection_only"] is True
    assert "INFISICAL_TOKEN" in manifest["prohibited_repository_keys"]
    assert set(manifest["fail_closed_feature_flags"].values()) == {"false"}


def test_production_template_keeps_sensitive_values_as_placeholders() -> None:
    env = (ROOT / ".env.production.example").read_text()

    assert "Never commit real secrets" in env
    assert "Use a secret manager for cloud deployments" in env
    assert "MAESTRO_TOP_UP_PURCHASE_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED=false" in env
    assert "replace_with_long_random_jwt_secret" in env
