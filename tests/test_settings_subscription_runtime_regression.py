from __future__ import annotations

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_router
from processual_api.routers import settings_subscription_runtime


def _subscription_get_routes() -> list[APIRoute]:
    return [
        route
        for route in settings_router.router.routes
        if isinstance(route, APIRoute)
        and route.path == "/settings/subscription"
        and "GET" in route.methods
    ]


def test_runtime_subscription_route_is_the_only_registered_get() -> None:
    routes = _subscription_get_routes()

    assert len(routes) == 1
    assert routes[0].endpoint is settings_subscription_runtime.get_runtime_subscription


def test_runtime_subscription_extension_targets_primary_settings_router() -> None:
    assert settings_subscription_runtime.settings_router is settings_router.router


def test_legacy_subscription_runtime_symbols_are_retired_after_extension_install() -> None:
    assert not hasattr(settings_router, "_load_billing_subscriptions")
    assert not hasattr(settings_router, "_compute_stage")
    assert not hasattr(settings_router, "get_subscription")


def test_plan_resolution_is_replaced_without_legacy_billing_file_dependency() -> None:
    assert (
        settings_router._resolve_client_api_key_integration_plan_id
        is settings_subscription_runtime.resolve_client_integration_plan_without_legacy_storage
    )
    assert (
        settings_router._resolve_current_plan_id
        is settings_subscription_runtime.resolve_current_plan_without_legacy_storage
    )
