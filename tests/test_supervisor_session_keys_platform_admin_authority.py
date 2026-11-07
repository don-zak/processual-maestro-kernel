from pathlib import Path

from fastapi.routing import APIRoute

from processual_api.routers import settings as settings_routes


CREATE_PATH = "/settings/admin/supervisor-session-keys"
REVOKE_PATH = "/settings/admin/supervisor-session-keys/{session_key_id}/revoke"


def _routes(path: str, method: str) -> list[APIRoute]:
    return [
        route
        for route in settings_routes.router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in route.methods
    ]


def test_supervisor_session_key_routes_are_registered_once_with_authoritative_wrappers() -> None:
    get_routes = _routes(CREATE_PATH, "GET")
    post_routes = _routes(CREATE_PATH, "POST")
    revoke_routes = _routes(REVOKE_PATH, "POST")

    assert len(get_routes) == 1
    assert len(post_routes) == 1
    assert len(revoke_routes) == 1

    assert get_routes[0].endpoint.__name__ == "list_admin_supervisor_session_keys_authoritative"
    assert post_routes[0].endpoint.__name__ == "create_admin_supervisor_session_key_authoritative"
    assert revoke_routes[0].endpoint.__name__ == "revoke_admin_supervisor_session_key_authoritative"


def test_supervisor_session_key_authority_extension_uses_canonical_platform_admin_guard() -> None:
    source = Path(
        "processual_api/routers/settings_supervisor_session_keys_authority.py"
    ).read_text(encoding="utf-8")

    assert "require_active_platform_admin" in source
    assert source.count("await require_active_platform_admin(current_user, request=request)") == 3
    assert "Depends(get_current_user)" in source
    assert "require_scope(" not in source
    assert "ADMIN_SETTINGS_SCOPE" not in source


def test_supervisor_session_key_mutations_pass_request_to_enforce_recent_mfa() -> None:
    source = Path(
        "processual_api/routers/settings_supervisor_session_keys_authority.py"
    ).read_text(encoding="utf-8")

    assert "request: Request" in source
    assert '@settings_module.router.post(\n    "/admin/supervisor-session-keys"' in source
    assert '"/admin/supervisor-session-keys/{session_key_id}/revoke"' in source
    assert "await require_active_platform_admin(current_user, request=request)" in source
