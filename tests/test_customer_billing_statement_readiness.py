from processual_api.api_readiness import (
    ApiReadiness,
    ApiVisibility,
    production_surface_allowed,
    readiness_for_path,
)


def test_customer_billing_statements_have_explicit_qualified_readiness():
    policy = readiness_for_path("/billing/statements/2026-08")
    assert policy is not None
    assert policy.surface_id == "billing_statements_customer"
    assert policy.visibility is ApiVisibility.CUSTOMER
    assert policy.readiness is ApiReadiness.SANDBOX_ONLY
    assert policy.auth_required is True
    assert policy.audit_required is True
    assert policy.production_allowed is False
    assert production_surface_allowed("/billing/statements/2026-08") is False


def test_supervisor_billing_statements_have_explicit_qualified_readiness():
    policy = readiness_for_path(
        "/billing/admin/statements/MUS-2026-08-client/pdf"
    )
    assert policy is not None
    assert policy.surface_id == "billing_statements_admin"
    assert policy.visibility is ApiVisibility.ADMIN
    assert policy.readiness is ApiReadiness.SANDBOX_ONLY
    assert policy.auth_required is True
    assert policy.audit_required is True
    assert policy.production_allowed is False
