from processual_api.api_readiness import (
    API_SURFACE_POLICIES,
    ApiReadiness,
    ApiVisibility,
    production_surface_allowed,
    readiness_for_path,
    validate_api_readiness_registry,
)


def test_api_readiness_registry_validates() -> None:
    validate_api_readiness_registry()


def test_customer_production_surfaces_are_explicitly_ready() -> None:
    for surface_id in (
        "workflows",
        "cgt",
        "governance",
        "reports",
        "provider_connection",
    ):
        policy = API_SURFACE_POLICIES[surface_id]
        assert policy.visibility is ApiVisibility.CUSTOMER
        assert policy.readiness is ApiReadiness.PRODUCTION_READY
        assert policy.production_allowed is True
        assert policy.auth_required is True


def test_advanced_integration_cannot_be_promoted_by_readiness_registry() -> None:
    policy = readiness_for_path("/settings/enterprise-integration/cases")
    assert policy is not None
    assert policy.readiness is ApiReadiness.SANDBOX_ONLY
    assert policy.production_allowed is False
    assert production_surface_allowed("/settings/enterprise-integration/cases") is False


def test_durable_execution_remains_internal_and_non_production() -> None:
    policy = readiness_for_path("/internal/execution/runs/example")
    assert policy is not None
    assert policy.visibility is ApiVisibility.INTERNAL
    assert policy.readiness is ApiReadiness.INTERNAL_ONLY
    assert policy.production_allowed is False
    assert production_surface_allowed("/internal/execution/runs/example") is False


def test_public_topup_purchase_remains_disabled_until_qualified() -> None:
    policy = readiness_for_path("/billing/topups/purchase")
    assert policy is not None
    assert policy.visibility is ApiVisibility.CUSTOMER
    assert policy.readiness is ApiReadiness.DISABLED
    assert policy.production_allowed is False
    assert production_surface_allowed("/billing/topups/purchase") is False


def test_admin_marketplace_is_not_misclassified_as_customer_surface() -> None:
    policy = readiness_for_path("/admin-marketplace/offers")
    assert policy is not None
    assert policy.visibility is ApiVisibility.ADMIN
    assert policy.auth_required is True
    assert policy.audit_required is True


def test_unknown_surface_fails_closed_for_production() -> None:
    assert readiness_for_path("/new-unclassified-customer-api") is None
    assert production_surface_allowed("/new-unclassified-customer-api") is False
