"""Idempotent registration for the standalone External Evaluation surface.

The application includes the long-lived Settings and CGT Governor routers.  The
External Evaluation handlers live in extension modules, so register their public
surface explicitly after every router extension has been imported.  Replacing
only the exact method/path pairs keeps startup deterministic without changing
handler, dependency, request-model, or authority semantics.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from . import cgt_governor as cgt_module
from . import settings as settings_module
from .evaluation_runtime import execute_evaluation_runtime_task
from .settings_admin_evaluation_grants import (
    create_evaluation_grant,
    evaluation_access_catalog,
    evaluation_grant_authority,
    evaluation_task_catalog,
    issue_evaluation_key,
    list_evaluation_grants,
    revoke_evaluation_grant,
)


def _route_matches(route: Any, path: str, method: str) -> bool:
    methods = getattr(route, "methods", set()) or set()
    return getattr(route, "path", "") == path and method.upper() in methods


def _replace_route(
    router: APIRouter,
    *,
    registered_path: str,
    add_path: str,
    method: str,
    endpoint: Callable[..., Any],
    status_code: int = 200,
    tags: list[str] | None = None,
) -> None:
    router.routes = [
        route
        for route in router.routes
        if not _route_matches(route, registered_path, method)
    ]
    router.add_api_route(
        add_path,
        endpoint,
        methods=[method],
        response_model=dict,
        status_code=status_code,
        tags=tags,
    )


def register_external_evaluation_routes() -> None:
    """Register the complete External Evaluation lifecycle exactly once."""

    _replace_route(
        cgt_module.router,
        registered_path="/evaluation/runtime/task-execute",
        add_path="/evaluation/runtime/task-execute",
        method="POST",
        endpoint=execute_evaluation_runtime_task,
        tags=["evaluation-runtime"],
    )

    admin_routes = (
        (
            "/settings/admin/evaluation-grants/authority",
            "/admin/evaluation-grants/authority",
            "GET",
            evaluation_grant_authority,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/access-catalog",
            "/admin/evaluation-grants/access-catalog",
            "GET",
            evaluation_access_catalog,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/task-catalog",
            "/admin/evaluation-grants/task-catalog",
            "GET",
            evaluation_task_catalog,
            200,
        ),
        (
            "/settings/admin/evaluation-grants",
            "/admin/evaluation-grants",
            "POST",
            create_evaluation_grant,
            201,
        ),
        (
            "/settings/admin/evaluation-grants",
            "/admin/evaluation-grants",
            "GET",
            list_evaluation_grants,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/issue-key",
            "/admin/evaluation-grants/{grant_id}/issue-key",
            "POST",
            issue_evaluation_key,
            201,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}",
            "/admin/evaluation-grants/{grant_id}",
            "DELETE",
            revoke_evaluation_grant,
            200,
        ),
    )
    for registered_path, add_path, method, endpoint, status_code in admin_routes:
        _replace_route(
            settings_module.router,
            registered_path=registered_path,
            add_path=add_path,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        )


register_external_evaluation_routes()


__all__ = ["register_external_evaluation_routes"]
