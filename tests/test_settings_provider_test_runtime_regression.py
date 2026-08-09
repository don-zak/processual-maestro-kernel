from __future__ import annotations

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router
from processual_api.routers import settings_provider_test_runtime


def _post_route(path: str) -> APIRoute:
    routes = [
        route
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in route.methods
    ]
    assert len(routes) == 1
    return routes[0]


def test_canonical_provider_test_route_uses_runtime_endpoint() -> None:
    route = _post_route("/settings/provider-connection/test")

    assert route.endpoint is settings_provider_test_runtime.test_provider_connection_runtime
    assert route.deprecated is not True


def test_legacy_provider_test_route_is_deprecated_compatibility_wrapper() -> None:
    route = _post_route("/settings/llm-provider/test")

    assert route.endpoint is settings_provider_test_runtime.test_legacy_llm_provider_runtime
    assert route.deprecated is True


def test_provider_test_routes_share_one_runtime_helper() -> None:
    source = settings_provider_test_runtime

    assert callable(source.run_provider_connection_test)
    assert source.settings_router is settings_router.router


def test_runtime_helper_preserves_secret_safe_failure_contract() -> None:
    optional = settings_provider_test_runtime._SECRET_OPTIONAL_PROVIDERS

    assert optional == {"opencode", "generic_openai_compatible"}
