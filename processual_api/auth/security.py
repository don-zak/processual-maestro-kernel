from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ..services.api_key_store import verify_dynamic_api_key
from ..settings import settings

try:
    from jose import JWTError, jwt
except ImportError:
    jwt: Any = None  # type: ignore[no-redef]
    JWTError: type[Exception] = Exception  # type: ignore[no-redef]

class _PBKDF2CompatBcrypt:
    """Tiny bcrypt-compatible fallback for minimal local/test environments.

    It exposes the hashpw/checkpw/gensalt subset used by this module while
    storing hashes in the module's pbkdf2_sha256 format. Production installs
    should still use the real bcrypt dependency declared in pyproject.toml.
    """

    @staticmethod
    def gensalt() -> bytes:
        return b""

    @staticmethod
    def hashpw(password: bytes, _salt: bytes) -> bytes:
        return _pbkdf2_hash_api_key(password.decode("utf-8")).encode("utf-8")

    @staticmethod
    def checkpw(password: bytes, hashed_password: bytes) -> bool:
        return _verify_pbkdf2_api_key(password.decode("utf-8"), hashed_password.decode("utf-8"))


try:
    import bcrypt as _bcrypt_lib
except ImportError:
    _bcrypt_lib = _PBKDF2CompatBcrypt()  # type: ignore[assignment]

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


def _get_jwt_secret() -> str:
    return settings.jwt_secret


def _get_jwt_algorithm() -> str:
    return settings.jwt_algorithm


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if jwt is None:
        raise RuntimeError("python-jose is not installed. Install with: pip install python-jose[cryptography]")
    expire = datetime.now(UTC) + (
        expires_delta if expires_delta is not None else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(UTC)}
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_get_jwt_algorithm())


def verify_access_token(token: str) -> dict:
    if jwt is None:
        raise RuntimeError("python-jose is not installed. Install with: pip install python-jose[cryptography]")
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_get_jwt_algorithm()])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def _pbkdf2_hash_api_key(api_key: str, *, iterations: int = 260_000) -> str:
    """Hash API keys with a stdlib fallback when bcrypt is unavailable.

    Production deployments should install bcrypt, but the fallback keeps local
    tests and minimal installations from failing with a 500 on /auth/api-key.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", api_key.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def _verify_pbkdf2_api_key(plain_key: str, hashed_key: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = hashed_key.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", plain_key.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def hash_api_key(api_key: str) -> str:
    if _bcrypt_lib is None:
        raise RuntimeError("bcrypt is not installed. Install with: pip install bcrypt")
    return _bcrypt_lib.hashpw(api_key.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    if hashed_key.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2_api_key(plain_key, hashed_key)
    if _bcrypt_lib is None:
        raise RuntimeError("bcrypt is not installed. Install with: pip install bcrypt")
    return _bcrypt_lib.checkpw(plain_key.encode("utf-8"), hashed_key.encode("utf-8"))


def generate_api_key() -> str:
    return f"pmk_{secrets.token_urlsafe(32)}"


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key_header),
) -> dict:
    if bearer:
        payload = verify_access_token(bearer.credentials)
        subject = payload.get("sub", "unknown")
        user = {
            "sub": subject,
            "user_id": subject,
            "client_id": payload.get("client_id", subject),
            "role": payload.get("role", "client"),
            "auth_method": "jwt",
            "session_type": payload.get("session_type", "jwt"),
            "scopes": payload.get("scopes", []),
        }
        request.state.current_user = user
        return user

    if api_key:
        dynamic_user = verify_dynamic_api_key(api_key)
        if dynamic_user:
            request.state.current_user = dynamic_user
            return dynamic_user

        app_env = os.environ.get("APP_ENV", settings.environment).lower()
        runtime_env = os.environ.get("ENVIRONMENT", settings.environment).lower()
        allow_env_fallback = (
            app_env in {"dev", "development", "local", "test"}
            and runtime_env not in {"production", "prod"}
            and not settings.is_production
        )


        if allow_env_fallback:
            for stored_key in settings.api_keys:
                if secrets.compare_digest(api_key, stored_key):
                    user = {
                        "sub": "api_key_user",
                        "user_id": "api_key_user",
                        "client_id": "dev",
                        "role": "dev",
                        "auth_method": "api_key",
                        "session_type": "api_key_env_fallback",
                        "api_key_id": "env",
                        "api_key_prefix": "env",
                        "scopes": ["*"],
                    }
                    request.state.current_user = user
                    return user

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a Bearer token or X-API-Key header.",
    )

def require_scope(required_scope: str):
    async def _scope_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        scopes = current_user.get("scopes", [])

        if "*" in scopes:
            return current_user

        if required_scope in scopes:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {required_scope}",
        )

    return _scope_dependency

def require_quota(quota_scope: str = "evaluation"):
    async def _quota_dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        from ..services.quota_store import consume_quota

        checked_user = consume_quota(
            current_user,
            method=request.method,
            endpoint=request.url.path,
            quota_scope=quota_scope,
        )
        request.state.current_user = checked_user
        return checked_user

    return _quota_dependency
