import asyncio

from fastapi import FastAPI
from starlette.requests import Request

from processual_api.integrations.api_key_access_policy import (
    list_api_key_access_policies,
)
from processual_api.integrations.api_key_operational_profiles import (
    list_api_key_operational_profiles,
)
from processual_api.integrations.api_key_platform_operational_profiles import (
    list_platform_api_key_operational_profiles,
)
from processual_api.routers.settings_admin_api_key_provisioning import (
    admin_api_key_access_catalog,
)


def _catalog_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health/live")
    async def health_live() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict:
        return {"status": "ok"}

    @app.get("/adapters/status")
    async def adapters_status() -> dict:
        return {"status": "ok"}

    @app.get("/cgt/govern/status")
    async def governor_status() -> dict:
        return {"status": "ok"}

    @app.post("/cgt/analyze")
    async def analyze() -> dict:
        return {"status": "ok"}

    @app.post("/cgt/govern")
    async def govern() -> dict:
        return {"status": "ok"}

    @app.get("/cgt/govern/reports")
    async def reports() -> dict:
        return {"status": "ok"}

    @app.post("/evaluation/runtime/task-execute")
    async def evaluation_task_execute() -> dict:
        return {"status": "ok"}

    @app.get("/runtime/new-route")
    async def undeclared_runtime_route() -> dict:
        return {"status": "locked"}

    @app.get("/settings/admin/example")
    async def control_plane_route() -> dict:
        return {"status": "locked"}

    return app


def _request(app: FastAPI) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/settings/admin/api-key-access-catalog",
            "headers": [],
            "app": app,
        }
    )


def test_every_canonical_access_policy_is_complete_and_non_admin() -> None:
    policies = list_api_key_access_policies()

    assert policies
    assert len({policy.task_id for policy in policies}) == len(policies)
    for policy in policies:
        assert policy.task_id.startswith("platform.")
        assert policy.operation_class in {"read", "execute"}
        assert policy.required_scopes
        assert policy.operational_profile_ids
        assert policy.production_allowed is False
        assert not policy.path.startswith(("/settings", "/admin", "/auth"))
        assert not any(
            scope == "*" or scope.startswith("admin:")
            for scope in policy.required_scopes
        )


def test_policy_profiles_exist_and_allow_every_required_scope() -> None:
    profiles = {
        str(profile["profile_id"]): profile
        for profile in (
            *list_api_key_operational_profiles(),
            *list_platform_api_key_operational_profiles(),
        )
    }

    for policy in list_api_key_access_policies():
        for profile_id in policy.operational_profile_ids:
            profile = profiles[profile_id]
            allowed = {str(scope) for scope in profile["allowed_scopes"]}
            assert set(policy.required_scopes).issubset(allowed)
            assert profile["production_allowed"] is False
            assert profile["runtime_connector_approved"] is False


def test_access_catalog_exposes_method_path_scope_task_profile_chain() -> None:
    payload = asyncio.run(
        admin_api_key_access_catalog(
            _request(_catalog_app()),
            {"role": "security_admin", "scopes": ["admin:api_keys:write"]},
        )
    )

    assert payload["policy_authority"] == "canonical_runtime_access_policy"
    assert payload["grantable_endpoint_count"] == 8
    assert payload["canonical_task_count"] == 8
    assert payload["canonical_tasks"]
    assert payload["operational_profile_ids"] == [
        "platform_evaluation_runtime",
        "platform_governor_sandbox",
        "platform_runtime_observability",
    ]

    by_key = {
        (endpoint["method"], endpoint["path"]): endpoint
        for endpoint in payload["endpoints"]
    }
    govern = by_key[("POST", "/cgt/govern")]
    assert govern["required_scopes"] == ["run:govern"]
    assert govern["task_id"] == "platform.cgt.govern"
    assert govern["operation_class"] == "execute"
    assert govern["operational_profile_ids"] == ["platform_governor_sandbox"]
    assert govern["selection_reason"] == "canonical_runtime_access_policy"

    evaluation = by_key[("POST", "/evaluation/runtime/task-execute")]
    assert evaluation["required_scopes"] == ["run:evaluation"]
    assert evaluation["operational_profile_ids"] == ["platform_evaluation_runtime"]
    assert evaluation["production_allowed"] is False


def test_undeclared_and_control_plane_routes_fail_closed() -> None:
    payload = asyncio.run(
        admin_api_key_access_catalog(
            _request(_catalog_app()),
            {"role": "security_admin", "scopes": ["admin:api_keys:write"]},
        )
    )
    by_key = {
        (endpoint["method"], endpoint["path"]): endpoint
        for endpoint in payload["endpoints"]
    }

    undeclared = by_key[("GET", "/runtime/new-route")]
    assert undeclared["grantable"] is False
    assert undeclared["task_id"] is None
    assert undeclared["required_scopes"] == []
    assert undeclared["operational_profile_ids"] == []

    control_plane = by_key[("GET", "/settings/admin/example")]
    assert control_plane["grantable"] is False
    assert control_plane["control_plane"] is True
