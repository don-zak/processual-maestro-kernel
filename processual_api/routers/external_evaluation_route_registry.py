"""Idempotent registration for the standalone External Evaluation surface.

The application includes the long-lived Settings and CGT Governor routers. The
External Evaluation handlers live in extension modules, so register their public
surface explicitly after every router extension has been imported. Replacing
only the exact method/path pairs keeps startup deterministic without changing
handler, dependency, request-model, or authority semantics.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from . import cgt_governor as cgt_module
from . import settings as settings_module
from .evaluation_cgt_runtime import governed_execute_evaluation_runtime_task
from .evaluation_cgt_status import evaluation_runtime_status_with_governance
from .evaluation_runtime import evaluation_runtime_execution_status
from .settings_admin_evaluation_grants import (
    evaluation_access_catalog,
    evaluation_grant_authority,
    evaluation_task_catalog,
    issue_evaluation_key,
    list_evaluation_grants,
    revoke_evaluation_grant,
)
from .settings_admin_evaluation_key_lifecycle import (
    acknowledge_evaluation_key_receipt,
    confirm_evaluation_key_delivery,
    list_evaluation_audit_report_receipts,
    list_evaluation_keys,
    revoke_evaluation_key,
)
from .settings_admin_evaluation_launch import issue_evaluation_workspace_launch
from .settings_admin_evaluation_quota_policy import (
    create_quota_governed_evaluation_grant,
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

    runtime_routes = (
        (
            "/evaluation/runtime/status",
            "/evaluation/runtime/status",
            "GET",
            evaluation_runtime_status_with_governance,
            200,
        ),
        (
            "/evaluation/runtime/executions/{execution_id}",
            "/evaluation/runtime/executions/{execution_id}",
            "GET",
            evaluation_runtime_execution_status,
            200,
        ),
        (
            "/evaluation/runtime/task-execute",
            "/evaluation/runtime/task-execute",
            "POST",
            governed_execute_evaluation_runtime_task,
            200,
        ),
    )
    for registered_path, add_path, method, endpoint, status_code in runtime_routes:
        _replace_route(
            cgt_module.router,
            registered_path=registered_path,
            add_path=add_path,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
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
            create_quota_governed_evaluation_grant,
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
            "/settings/admin/evaluation-grants/{grant_id}/issue-launch",
            "/admin/evaluation-grants/{grant_id}/issue-launch",
            "POST",
            issue_evaluation_workspace_launch,
            201,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/keys",
            "/admin/evaluation-grants/{grant_id}/keys",
            "GET",
            list_evaluation_keys,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/audit-receipts",
            "/admin/evaluation-grants/{grant_id}/audit-receipts",
            "GET",
            list_evaluation_audit_report_receipts,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}/confirm-delivery",
            "/admin/evaluation-grants/{grant_id}/keys/{key_id}/confirm-delivery",
            "POST",
            confirm_evaluation_key_delivery,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}/acknowledge",
            "/admin/evaluation-grants/{grant_id}/keys/{key_id}/acknowledge",
            "POST",
            acknowledge_evaluation_key_receipt,
            200,
        ),
        (
            "/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}",
            "/admin/evaluation-grants/{grant_id}/keys/{key_id}",
            "DELETE",
            revoke_evaluation_key,
            200,
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
