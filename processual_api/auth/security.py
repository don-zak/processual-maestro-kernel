from __future__ import annotations

import os
import sys

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from processual_api.auth import security_legacy as _legacy
from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    verify_evaluation_api_key,
)
from processual_api.services.evaluation_grants import evaluation_endpoint_allowed
from processual_api.settings import settings

# Keep static analysis aware of the stable security surface. Runtime exposes the
# legacy module object itself below, so monkeypatches continue to target the
# globals used by the historical implementation rather than a proxy copy.
_pbkdf2_hash_api_key = _legacy._pbkdf2_hash_api_key
_verify_pbkdf2_api_key = _legacy._verify_pbkdf2_api_key
_PBKDF2CompatBcrypt = _legacy._PBKDF2CompatBcrypt
generate_api_key = _legacy.generate_api_key
hash_api_key = _legacy.hash_api_key
verify_api_key = _legacy.verify_api_key
create_access_token = _legacy.create_access_token
verify_access_token = _legacy.verify_access_token

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_supervisor_session_key_header = APIKeyHeader(name="X-Supervisor-Session-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)
_legacy_get_current_user = _legacy.get_current_user


def _production_runtime() -> bool:
    app_env = os.environ.get("APP_ENV", settings.environment).lower()
    runtime_env = os.environ.get("ENVIRONMENT", settings.environment).lower()
    return (
        settings.is_production
        or app_env in {"production", "prod"}
        or runtime_env in {"production", "prod"}
    )


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key_header),
    supervisor_session_key: str | None = Depends(_supervisor_session_key_header),
) -> dict:
    if api_key and not bearer:
        try:
            shared_user = await verify_evaluation_api_key(api_key)
        except EvaluationAuthorityError:
            # Authentication remains fail-closed for an unverified Evaluation
            # key, while unrelated dynamic API keys keep their own authority.
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

    user = await _legacy_get_current_user(
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


# Dependency factories in the implementation module resolve get_current_user
# from their module globals, so install the shared-first dependency there.
_legacy.get_current_user = get_current_user

# Return the implementation module itself instead of a copied proxy namespace.
# This preserves historical monkeypatch and FastAPI dependency behavior.
sys.modules[__name__] = _legacy
