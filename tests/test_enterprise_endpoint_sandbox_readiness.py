from __future__ import annotations

from fastapi.routing import APIRoute

from processual_api.api_readiness import (
    ApiReadiness,
    ApiVisibility,
    production_surface_allowed,
    readiness_for_path,
)
from processual_api.routers import settings as settings_router


CLIENT_PATHS = (
    "/settings/enterprise-integration/task-catalog",
    "/settings/enterprise-integration/endpoint-bindings",
    "/settings/enterprise-integration/endpoint-bindings/{binding_id}/request-mapping",
    "/settings/enterprise-integration/endpoint-bindings/{binding_id}/request-preview",
    "/settings/enterprise-integration/endpoint-bindings/{binding_id}/mapping-preview",
    "/settings/enterprise-integration/endpoint-bindings/{binding_id}/sandbox-execute",
    "/settings/enterprise-integration/sandbox-evidence",
)
ADMIN_GRANT_PATH = (
    "/settings/admin/integration-tasks/{client_id}/endpoint-bindings/"
    "{binding_id}/sandbox-grant"
)


def test_all_sandbox_proof_routes_are_registered() -> None:
    paths = {
        route.path
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
    }
    for path in CLIENT_PATHS:
        assert path in paths
    assert ADMIN_GRANT_PATH in paths


def test_customer_sandbox_proof_routes_remain_sandbox_only() -> None:
    for path in CLIENT_PATHS:
        policy = readiness_for_path(path)
        assert policy is not None
        assert policy.surface_id == "advanced_integration"
        assert policy.visibility is ApiVisibility.CUSTOMER
        assert policy.readiness is ApiReadiness.SANDBOX_ONLY
        assert policy.production_allowed is False
        assert production_surface_allowed(path) is False


def test_supervisor_grant_route_reuses_sandbox_admin_authority() -> None:
    policy = readiness_for_path(ADMIN_GRANT_PATH)
    assert policy is not None
    assert policy.surface_id == "integration_tasks_admin"
    assert policy.visibility is ApiVisibility.ADMIN
    assert policy.readiness is ApiReadiness.SANDBOX_ONLY
    assert policy.auth_required is True
    assert policy.audit_required is True
    assert policy.production_allowed is False
    assert production_surface_allowed(ADMIN_GRANT_PATH) is False
