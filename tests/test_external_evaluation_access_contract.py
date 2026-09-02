from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from processual_api.integrations.api_key_access_policy import get_api_key_access_policy
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    evaluation_endpoint_allowed,
    validate_evaluation_grant,
)

ROOT = Path(__file__).resolve().parents[1]


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
        "allowed_binding_ids": ["binding_crm_eval"],
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
        requested_binding_ids=["binding_crm_eval"],
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
            requested_binding_ids=[],
            quota_limit=25,
        )


def test_legacy_grant_without_endpoint_envelope_requires_reissue() -> None:
    grant = _grant()
    grant.pop("allowed_endpoints")
    raw = {"evaluation_grants_v1": [grant]}
    with pytest.raises(ValueError, match="evaluation_grant_endpoints_required"):
        validate_evaluation_grant(
            raw,
            grant_id="eval_contract",
            client_id="external-evaluator",
            requested_scopes=["read:health", "run:evaluation"],
            requested_endpoints=[{"method": "GET", "path": "/health/live"}],
            requested_task_ids=["crm.customer_context"],
            requested_binding_ids=[],
            quota_limit=25,
        )


def test_runtime_grant_without_binding_envelope_requires_reissue() -> None:
    grant = _grant()
    grant.pop("allowed_binding_ids")
    raw = {"evaluation_grants_v1": [grant]}
    with pytest.raises(ValueError, match="evaluation_grant_bindings_required"):
        validate_evaluation_grant(
            raw,
            grant_id="eval_contract",
            client_id="external-evaluator",
            requested_scopes=["read:health", "run:evaluation"],
            requested_endpoints=list(grant["allowed_endpoints"]),
            requested_task_ids=["crm.customer_context"],
            requested_binding_ids=[],
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


def test_external_evaluation_routes_are_unique_in_clean_startup() -> None:
    routes = [
        ("POST", "/evaluation/runtime/task-execute"),
        ("GET", "/settings/admin/evaluation-grants/authority"),
        ("GET", "/settings/admin/evaluation-grants/access-catalog"),
        ("GET", "/settings/admin/evaluation-grants/binding-catalog"),
        ("POST", "/settings/admin/evaluation-grants"),
        ("GET", "/settings/admin/evaluation-grants"),
    ]
    script = """
import json
import processual_api
from fastapi.routing import APIRoute
from processual_api.main import app
import processual_api.routers

wanted = __ROUTES__


def iter_api_routes(route_collection, seen=None):
    if seen is None:
        seen = set()
    collection_id = id(route_collection)
    if collection_id in seen:
        return
    seen.add(collection_id)
    for route in route_collection:
        if isinstance(route, APIRoute):
            yield route
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            nested = getattr(original_router, "routes", None)
            if nested is not None:
                yield from iter_api_routes(nested, seen)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from iter_api_routes(nested, seen)


resolved_routes = list(iter_api_routes(app.routes))
counts = {}
for method, path in wanted:
    counts[f"{method} {path}"] = sum(
        1
        for route in resolved_routes
        if route.path == path
        and method in (route.methods or set())
    )

print(json.dumps({
    "processual_api_file": processual_api.__file__,
    "routers_file": processual_api.routers.__file__,
    "resolved_api_route_count": len(resolved_routes),
    "counts": counts,
}, sort_keys=True))
""".replace("__ROUTES__", repr(routes))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert Path(payload["processual_api_file"]).resolve().is_relative_to(ROOT)
    assert Path(payload["routers_file"]).resolve().is_relative_to(ROOT)
    assert payload["counts"] == {f"{method} {path}": 1 for method, path in routes}, payload
