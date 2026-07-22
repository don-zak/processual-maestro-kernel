from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ..admin_audit_log import append_admin_audit_event
from ..services.api_key_store import verify_dynamic_api_key
from ..settings import settings
from ..supervisor_session_keys import validate_supervisor_session_key

try:
    import jwt
    from jwt import PyJWTError
except ImportError:
    jwt: Any = None  # type: ignore[no-redef]
    PyJWTError: type[Exception] = Exception  # type: ignore[no-redef]

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
_supervisor_session_key_header = APIKeyHeader(name="X-Supervisor-Session-Key", auto_error=False)
_bearer = HTTPBearer(auto_error=False)


def _supervisor_session_key_store_path() -> Path:
    configured = os.environ.get("PMK_SUPERVISOR_SESSION_KEYS_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("data") / "supervisor_session_keys.json"


def _auth_admin_audit_path() -> Path:
    configured = os.environ.get("PMK_ADMIN_AUDIT_LOG_PATH", "").strip()
    if configured:
        return Path(configured)
    return Path("data") / "admin_audit.jsonl"


def _supervisor_actor_level_for_audit(user: dict[str, Any]) -> str:
    return str(
        user.get("supervision_level")
        or user.get("supervisor_level")
        or "legacy_admin"
    )


def _supervisor_session_key_denial_reason(exc: PermissionError) -> str:
    detail = str(exc).lower()
    if "expired" in detail:
        return "expired_supervisor_session_key"
    if "revoked" in detail:
        return "revoked_supervisor_session_key"
    return "invalid_supervisor_session_key"


def _record_supervisor_session_key_denied(
    *,
    request: Request,
    user: dict[str, Any],
    reason: str,
) -> None:
    append_admin_audit_event(
        audit_path=_auth_admin_audit_path(),
        actor=str(user.get("email") or user.get("sub") or user.get("user_id") or "admin"),
        actor_level=_supervisor_actor_level_for_audit(user),
        action="supervisor_session_key_denied",
        target_type="supervisor_session",
        target_id=str(user.get("session_key_id") or "unknown"),
        source="auth",
        result="denied",
        reason=reason,
        request_path=str(request.url.path),
    )


def _merge_supervisor_session_user(
    user: dict[str, Any],
    session: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(user)
    session_key_id = str(session.get("session_key_id") or "")
    level = str(session.get("level") or "")

    merged["supervision_level"] = level
    merged["session_key_id"] = session_key_id
    merged["supervisor_session_key_id"] = session_key_id
    merged["supervisor_session_validated"] = True

    session_scopes = [
        str(scope)
        for scope in session.get("scopes") or []
        if str(scope or "").strip()
    ]
    merged["supervision_scopes"] = session_scopes

    existing_scopes = [
        str(scope)
        for scope in merged.get("scopes") or []
        if str(scope or "").strip()
    ]
    merged["scopes"] = sorted({*existing_scopes, *session_scopes})

    issued_to = str(session.get("issued_to") or "").strip()
    if issued_to:
        merged["supervisor_session_issued_to"] = issued_to

    session_label = str(session.get("session_label") or "").strip()
    if session_label:
        merged["supervisor_session_label"] = session_label

    return merged


def _apply_supervisor_session_header(
    *,
    request: Request,
    user: dict[str, Any],
    raw_supervisor_session_key: str | None,
) -> dict[str, Any]:
    raw_key = str(raw_supervisor_session_key or "").strip()
    if not raw_key:
        return user

    try:
        session = validate_supervisor_session_key(
            _supervisor_session_key_store_path(),
            raw_key,
        )
    except PermissionError as exc:
        reason = _supervisor_session_key_denial_reason(exc)
        _record_supervisor_session_key_denied(
            request=request,
            user=user,
            reason=reason,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor session key denied.",
        ) from exc

    return _merge_supervisor_session_user(user, session)



def _get_jwt_secret() -> str:
    return settings.jwt_secret


def _get_jwt_algorithm() -> str:
    return settings.jwt_algorithm


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    *,
    role: str = "client",
    client_id: str | None = None,
    session_type: str = "jwt",
    scopes: list[str] | None = None,
    session_id: str | None = None,
    organization_id: str | None = None,
    platform_authorities: tuple[str, ...] = (),
) -> str:
    if jwt is None:
        raise RuntimeError("PyJWT is not installed. Install with: pip install PyJWT[crypto]")
    now = datetime.now(UTC)
    expire = now + (
        expires_delta if expires_delta is not None else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "role": role,
        "client_id": client_id or subject,
        "session_type": session_type,
        "scopes": scopes or [],
        "platform_authorities": list(platform_authorities),
    }
    if session_id is not None:
        payload["sid"] = session_id
    if organization_id is not None:
        payload["organization_id"] = organization_id
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_get_jwt_algorithm())




def verify_access_token(token: str) -> dict:
    if jwt is None:
        raise RuntimeError("PyJWT is not installed. Install with: pip install PyJWT[crypto]")
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_get_jwt_algorithm()])
        return payload
    except PyJWTError:
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


async def _validate_identity_session(
    *,
    subject: str,
    session_id: str,
    organization_id: str | None,
) -> tuple[str, str | None, bool]:
    from sqlalchemy import select

    from processual_api.auth.models import (
        AuthMfaFactor,
        AuthSession,
        IdentityPlatformAuthority,
        IdentityUser,
        OrganizationMembership,
    )
    from processual_api.db.session import get_session_factory

    try:
        user_uuid = uuid.UUID(subject)
        session_uuid = uuid.UUID(session_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    try:
        session_factory = get_session_factory()
        async with session_factory() as db_session:
            row = (
                await db_session.execute(
                    select(AuthSession, IdentityUser)
                    .join(IdentityUser, IdentityUser.id == AuthSession.user_id)
                    .where(
                        AuthSession.id == session_uuid,
                        AuthSession.user_id == user_uuid,
                    )
                )
            ).one_or_none()
            active_mfa_factor_id = await db_session.scalar(
                select(AuthMfaFactor.id)
                .where(
                    AuthMfaFactor.user_id == user_uuid,
                    AuthMfaFactor.status == "active",
                )
                .limit(1)
            )
            privileged_membership_id = await db_session.scalar(
                select(OrganizationMembership.id)
                .where(
                    OrganizationMembership.user_id == user_uuid,
                    OrganizationMembership.status == "active",
                    OrganizationMembership.role.in_(("organization_owner", "organization_admin")),
                )
                .limit(1)
            )
            active_platform_admin_authority_id = await db_session.scalar(
                select(IdentityPlatformAuthority.id)
                .where(
                    IdentityPlatformAuthority.user_id == user_uuid,
                    IdentityPlatformAuthority.authority == "platform_admin",
                    IdentityPlatformAuthority.status == "active",
                )
                .limit(1)
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session authority unavailable",
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    auth_session, user = row
    now = datetime.now(UTC)
    authoritative_organization = (
        str(auth_session.organization_id) if auth_session.organization_id is not None else None
    )
    if (
        auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or user.status != "active"
        or organization_id != authoritative_organization
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    mfa_required = (
        active_mfa_factor_id is not None
        or privileged_membership_id is not None
        or active_platform_admin_authority_id is not None
    )
    mfa_pending = mfa_required and auth_session.mfa_satisfied_at is None
    return str(user.id), authoritative_organization, mfa_pending


async def get_current_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer),
    api_key: str | None = Depends(_api_key_header),
    supervisor_session_key: str | None = Depends(_supervisor_session_key_header),
) -> dict:
    if bearer:
        payload = verify_access_token(bearer.credentials)
        subject = payload.get("sub", "unknown")
        session_type = payload.get("session_type", "jwt")
        if session_type == "identity_user":
            session_id = payload.get("sid")
            if not isinstance(session_id, str):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                )
            subject, organization_id, mfa_pending = await _validate_identity_session(
                subject=str(subject),
                session_id=session_id,
                organization_id=payload.get("organization_id"),
            )
            user = {
                "sub": subject,
                "user_id": subject,
                "client_id": organization_id or subject,
                "organization_id": organization_id,
                "role": "client",
                "auth_method": "jwt",
                "session_type": "identity_user",
                "session_id": session_id,
                "scopes": ["auth:mfa"] if mfa_pending else ["evaluation"],
                "mfa_pending": mfa_pending,
                "mfa_satisfied_at": (
                    None if mfa_pending else payload.get("mfa_satisfied_at")
                ),
            }
            request.state.current_user = user
            return user
        user = {
            "sub": subject,
            "user_id": subject,
            "client_id": payload.get("client_id", subject),
            "role": payload.get("role", "client"),
            "auth_method": "jwt",
            "session_type": session_type,
            "scopes": payload.get("scopes", []),
        }
        user = _apply_supervisor_session_header(
            request=request,
            user=user,
            raw_supervisor_session_key=supervisor_session_key,
        )
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


def require_recent_mfa(max_age_seconds: int = 300):
    if max_age_seconds < 60 or max_age_seconds > 1800:
        raise ValueError("MFA step-up lifetime is outside its safe range.")

    async def _recent_mfa_dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("session_type") != "identity_user":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Identity session required.")
        try:
            session_id = uuid.UUID(str(current_user["session_id"]))
            user_id = uuid.UUID(str(current_user["user_id"]))
            from sqlalchemy import select

            from processual_api.auth.models import AuthSession
            from processual_api.db.session import get_session_factory

            async with get_session_factory()() as db_session:
                auth_session = await db_session.scalar(
                    select(AuthSession).where(
                        AuthSession.id == session_id,
                        AuthSession.user_id == user_id,
                    )
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session authority unavailable",
            ) from exc
        now = datetime.now(UTC)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or auth_session.mfa_satisfied_at is None
            or auth_session.mfa_satisfied_at < now - timedelta(seconds=max_age_seconds)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent MFA verification required.",
            )
        return current_user

    return _recent_mfa_dependency

def require_platform_admin_step_up(
    max_age_seconds: int | None = None,
):
    effective_max_age = (
        settings.auth_mfa_step_up_seconds
        if max_age_seconds is None
        else max_age_seconds
    )
    if effective_max_age < 60 or effective_max_age > 1800:
        raise ValueError(
            "Platform-admin step-up lifetime is outside its safe range."
        )

    async def _platform_admin_step_up_dependency(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user.get("session_type") != "identity_user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identity session required.",
            )
        try:
            session_id = uuid.UUID(str(current_user["session_id"]))
            user_id = uuid.UUID(str(current_user["user_id"]))

            from sqlalchemy import select

            from processual_api.auth.models import (
                AuthSession,
                IdentityPlatformAuthority,
            )
            from processual_api.db.session import get_session_factory

            async with get_session_factory()() as db_session:
                row = (
                    await db_session.execute(
                        select(
                            AuthSession,
                            IdentityPlatformAuthority,
                        )
                        .join(
                            IdentityPlatformAuthority,
                            IdentityPlatformAuthority.user_id
                            == AuthSession.user_id,
                        )
                        .where(
                            AuthSession.id == session_id,
                            AuthSession.user_id == user_id,
                            IdentityPlatformAuthority.authority
                            == "platform_admin",
                            IdentityPlatformAuthority.status == "active",
                        )
                    )
                ).one_or_none()
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform administrator step-up required.",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session authority unavailable",
            ) from exc

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active platform administrator authority required.",
            )

        auth_session, _platform_authority = row
        now = datetime.now(UTC)

        if (
            auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or auth_session.mfa_satisfied_at is None
            or auth_session.mfa_satisfied_at
            < now - timedelta(seconds=effective_max_age)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Recent MFA verification required.",
            )

        return current_user

    return _platform_admin_step_up_dependency


def require_quota(quota_scope: str = "evaluation"):
    async def _quota_dependency(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        from ..billing.usage_pricing import pricing_decision
        from ..services.quota_store import consume_quota

        pricing_item_count = getattr(request.state, "pricing_item_count", None)
        if not isinstance(pricing_item_count, int):
            pricing_item_count = None

        pricing = pricing_decision(
            request.url.path,
            item_count=pricing_item_count,
        )
        request.state.pricing_decision = pricing
        request.state.pricing_units_charged = pricing.units_charged

        try:
            checked_user = consume_quota(
                current_user,
                method=request.method,
                endpoint=request.url.path,
                quota_scope=quota_scope,
                amount=pricing.units_charged,
            )
        except HTTPException as exc:
            detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
            if detail.get("error") == "quota_exceeded":
                rejected_user = dict(current_user)
                rejected_user["quota_rejected"] = True
                rejected_user["quota"] = {
                    "scope": detail.get("quota_scope", quota_scope),
                    "plan_id": detail.get("plan_id", current_user.get("plan_id", "")),
                    "limit": detail.get("quota_limit"),
                    "used": detail.get("quota_used"),
                    "requested": detail.get(
                        "quota_requested",
                        pricing.units_charged,
                    ),
                    "remaining": detail.get("quota_remaining"),
                    "rejected": True,
                }
                request.state.current_user = rejected_user
            raise

        request.state.current_user = checked_user
        return checked_user

    return _quota_dependency
