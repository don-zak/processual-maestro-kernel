from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from . import security_legacy as _legacy
from ..services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    verify_evaluation_api_key,
)
from ..services.evaluation_grants import evaluation_endpoint_allowed
from ..settings import settings

# Preserve the complete historical security surface while overriding only the
# authentication dependencies that must consult shared Evaluation authority.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(_legacy, _name))

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_supervisor_session_key_header = APIKeyHeader(name="X-Supervisor-Session-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


def _production_runtime() -> bool:
    app_env = os.environ.get("APP_ENV", settings.environment).lower()
    runtime_env = os.environ.get("ENVIRONMENT", settings.environment).lower()
    return settings.is_production or app_env in {"production", "prod"} or runtime_env in {"production", "prod"}


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key_header),
    supervisor_session_key: str | None = Depends(_supervisor_session_key_header),
) -> dict:
    if api_key and not bearer:
        try:
            shared_user = await verify_evaluation_api_key(api_key)
        except EvaluationAuthorityError as exc:
            if _production_runtime():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Shared Evaluation authority is unavailable.",
                ) from exc
            shared_user = None

        if shared_user is not None:
            if not evaluation_endpoint_allowed(
                shared_user,
                method=request.method,
                path=request.url.path,
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Evaluation API key is not allowed for this endpoint.",
                )
            request.state.current_user = shared_user
            return shared_user

    user = await _legacy.get_current_user(
        request,
        bearer=bearer,
        api_key=api_key,
        supervisor_session_key=supervisor_session_key,
    )
    if (
        api_key
        and _production_runtime()
        and user.get("entitlement_source") == "admin_evaluation_grant"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Evaluation API key is not present in shared authority.",
        )
    return user


def require_scope(required_scope: str):
    async def _scope_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        scopes = current_user.get("scopes", [])
        if "*" in scopes or required_scope in scopes:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {required_scope}",
        )

    return _scope_dependency


def require_recent_mfa(max_age_seconds: int = 300):
    legacy_dependency = _legacy.require_recent_mfa(max_age_seconds)

    async def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        return await legacy_dependency(current_user)

    return _dependency


def require_platform_admin_step_up(max_age_seconds: int | None = None):
    legacy_dependency = _legacy.require_platform_admin_step_up(max_age_seconds)

    async def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        return await legacy_dependency(current_user)

    return _dependency


def require_quota(quota_scope: str = "evaluation"):
    legacy_dependency = _legacy.require_quota(quota_scope)

    async def _dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        return await legacy_dependency(request, current_user)

    return _dependency


__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in {"_legacy", "_name"}
]
