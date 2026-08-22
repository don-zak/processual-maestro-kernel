from __future__ import annotations

import json
from pathlib import Path

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.billing.maestro_units import MAESTRO_UNIT_METRIC, maestro_unit_rule
from processual_api.billing.plan_capability_matrix import (
    EXECUTION_CAPABILITY_POLICIES,
    CapabilityStatus,
    TOOL_CAPABILITIES,
    plan_can_execute,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS
from processual_api.billing.public_plan_journey import (
    RETIRED_PUBLIC_ENTERPRISE_PLAN_IDS,
    public_plan_journey_catalog,
)
from processual_api.release_gate import _REQUIRED_VALUES


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
        assert quota_profile.metrics[0].metric_code == MAESTRO_UNIT_METRIC


def test_public_plan_journey_never_claims_unbound_assessment_quota() -> None:
    catalog = public_plan_journey_catalog()
    plans = {item["plan_id"]: item for item in catalog["plans"]}

    direct_mapping = {
        "academic_individual": "academic",
        "starter": "starter",
        "business": "business",
    }
    for public_plan_id, fulfillment_plan_id in direct_mapping.items():
        plan = plans[public_plan_id]
        assert plan["requires_assessment"] is False
        assert plan["registration_available"] is True
        assert plan["included_quota_units"] == PLAN_FULFILLMENT_SPECS[
            fulfillment_plan_id
        ].monthly_unit_allowance

    assert set(plans).isdisjoint(RETIRED_PUBLIC_ENTERPRISE_PLAN_IDS)

    for plan in plans.values():
        if plan["requires_assessment"]:
            assert plan["registration_available"] is False
            assert plan["registration_path"] is None
            assert plan["included_quota_units"] is None

    trial = plans["enterprise_integration_starter"]
    assert trial["commercial_model"] == "requirements_based_evaluation"
    assert trial["quota_source"] == "approved_customer_scope"
    assert trial["fixed_public_price"] is False
    assert trial["trial"]["duration_days"] == 30
    assert trial["trial"]["termination_policy"] == (
        "30_days_or_agreed_quota_exhausted"
    )

    deployment = plans["enterprise_deployment"]
    assert deployment["commercial_model"] == "requirements_based_contract"
    assert deployment["quota_source"] == "approved_customer_scope"
    assert deployment["fixed_public_price"] is False
    assert deployment["trial"]["duration_days"] is None


def test_execution_rights_and_unit_costs_share_one_authority() -> None:
    for policy in EXECUTION_CAPABILITY_POLICIES.values():
        rule = maestro_unit_rule(policy.path)
        assert rule is not None
        assert policy.quota_metric == MAESTRO_UNIT_METRIC
        assert rule.units == policy.quota_cost
        assert rule.capability_code == policy.capability_code

    assert plan_can_execute("starter", "maestro_execution") is True
    assert plan_can_execute("starter", "enterprise_governance") is False
    # Historical entitlement capabilities remain internally readable until a
    # separately proven data migration retires persisted legacy plan references.
    assert plan_can_execute("enterprise_pilot", "enterprise_governance") is True

    advanced = TOOL_CAPABILITIES["advanced_integration"]
    assert advanced.status is CapabilityStatus.SANDBOX_ONLY
    assert advanced.production_allowed is False
    assert plan_can_execute(
        "enterprise_scale", "advanced_integration", require_production=True
    ) is False

    durable = TOOL_CAPABILITIES["durable_execution_internal"]
    assert durable.status is CapabilityStatus.INTERNAL_ONLY
    assert durable.customer_executable is False
    assert durable.production_allowed is False
    assert all(
        "durable_execution_internal" not in spec.entitlement_codes
        for spec in PLAN_FULFILLMENT_SPECS.values()
    )


def test_registration_activation_and_usage_are_bound_to_plan_authority() -> None:
    registration = (ROOT / "processual_api/auth/registration_service.py").read_text()
    activation = (
        ROOT / "processual_api/admin_marketplace/subscription_activation_service.py"
    ).read_text()
    usage = (
        ROOT / "processual_api/admin_marketplace/subscription_quota_usage.py"
    ).read_text()
    middleware = (ROOT / "processual_api/middleware/subscription.py").read_text()

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

    assert "required_execution_capability" in middleware
    assert "require_plan_entitlement" in middleware
    assert 'stage == "grace"' in middleware
    assert 'stage == "suspended"' in middleware
    assert 'stage == "terminated"' in middleware


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

    classified = [
        set(manifest["secret_keys"]),
        set(manifest["configuration_keys"]),
        set(manifest["real_staging_evidence_keys"]),
    ]
    assert not (classified[0] & classified[1])
    assert not (classified[0] & classified[2])
    assert not (classified[1] & classified[2])
    assert set().union(*classified) == set(_REQUIRED_VALUES)


def test_production_template_covers_release_gate_without_real_evidence() -> None:
    env = (ROOT / ".env.production.example").read_text()
    declared = {
        line.split("=", 1)[0]
        for line in env.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert "Never commit real secrets" in env
    assert "Use a secret manager for cloud deployments" in env
    assert set(_REQUIRED_VALUES).issubset(declared)
    assert "MIGRATION_BACKUP_REFERENCE=" in env
    assert "MIGRATION_RESTORE_REHEARSAL_REFERENCE=" in env
    assert "MAESTRO_TOP_UP_PURCHASE_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED=false" in env
    assert "replace_with_long_random_jwt_secret" in env


def test_cloud_run_container_honors_port_and_never_migrates_on_startup() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert dockerfile.count("${PORT:-8000}") >= 2
    assert "uvicorn processual_api.main:app" in dockerfile
    assert "alembic upgrade" not in dockerfile
