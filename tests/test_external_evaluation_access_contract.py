from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.routing import APIRoute

from processual_api.integrations.api_key_access_policy import get_api_key_access_policy
from processual_api.routers import cgt_governor, settings
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    evaluation_endpoint_allowed,
    validate_evaluation_grant,
)


def _grant() -> dict:
    return {
        "grant_id": "eval_contract",
        "status": "active",
        "client_id": "external-evaluator",
        "user_id": "owner-user",
        "issued_to": "external evaluator",
        "purpose": "controlled external API qualification",
        "allowed_task_ids": ["crm.customer_context"],
        "task_scope_ids": ["crm.read"],
        "allowed_endpoints": [
            {"method": "GET", "path": "/health/live"},
            {"method": "POST", "path": "/evaluation/runtime/task-execute"},
        ],
        "allowed_scopes": ["read:health", "run:evaluation"],
        "max_requests": 25,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "approved_by_role": "platform_admin",
        "subscription_required": False,
        "registration_required": False,
        "commercial_quota_required": False,
        "execution_mode": EVALUATION_EXECUTION_MODE,
        "real_runtime_execution": True,
        "production_allowed": False,
    }


def test_evaluation_runtime_endpoint_is_explicitly_grantable() -> None:
    policy = get_api_key_access_policy("POST", "/evaluation/runtime/task-execute")
    assert policy is not None
    assert policy.required_scopes == ("run:evaluation",)
    assert policy.production_allowed is False
    assert get_api_key_access_policy("POST", "/settings/api-keys") is None


def test_grant_validation_requires_exact_endpoint_envelope() -> None:
    grant = _grant()
    raw = {"evaluation_grants_v1": [grant]}
    assert validate_evaluation_grant(
        raw,
        grant_id="eval_contract",
        client_id="external-evaluator",
        requested_scopes=["read:health", "run:evaluation"],
        requested_endpoints=list(grant["allowed_endpoints"]),
        requested_task_ids=["crm.customer_context"],
        quota_limit=25,
    ) is grant

    with pytest.raises(ValueError, match="evaluation_grant_endpoint_mismatch"):
        validate_evaluation_grant(
            raw,
            grant_id="eval_contract",
            client_id="external-evaluator",
            requested_scopes=["read:health", "run:evaluation"],
            requested_endpoints=[{"method": "POST", "path": "/cgt/govern"}],
            requested_task_ids=["crm.customer_context"],
            quota_limit=25,
        )


def test_evaluation_endpoint_authority_fails_closed() -> None:
    identity = {
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "allowed_endpoints": [{"method": "GET", "path": "/health/live"}],
    }
    assert evaluation_endpoint_allowed(identity, method="GET", path="/health/live")
    assert not evaluation_endpoint_allowed(identity, method="GET", path="/settings")
    assert not evaluation_endpoint_allowed(identity, method="POST", path="/cgt/govern")


def test_external_evaluation_routes_are_unique() -> None:
    def count(router, path: str, method: str) -> int:
        return sum(
            1
            for route in router.routes
            if isinstance(route, APIRoute)
            and route.path == path
            and method in (route.methods or set())
        )

    assert count(cgt_governor.router, "/evaluation/runtime/task-execute", "POST") == 1
    assert count(settings.router, "/settings/admin/evaluation-grants/authority", "GET") == 1
    assert count(settings.router, "/settings/admin/evaluation-grants/access-catalog", "GET") == 1
    assert count(settings.router, "/settings/admin/evaluation-grants", "POST") == 1
    assert count(settings.router, "/settings/admin/evaluation-grants", "GET") == 1
