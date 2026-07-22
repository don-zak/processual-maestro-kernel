from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

from processual_api.auth.passwords import PasswordService
from processual_api.auth.rate_limit import RedisAuthRateLimiter, TrustedProxyPolicy
from processual_api.auth.session_repository import SqlAlchemySessionUnitOfWork
from processual_api.auth.session_service import SessionService
from processual_api.auth.token_material import TokenDigester
from processual_api.cache.redis import get_redis
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class SessionRuntimeUnavailableError(RuntimeError):
    """A required login or session authority is missing or invalid."""


@dataclass(frozen=True, slots=True)
class SessionRuntime:
    service: SessionService
    rate_limiter: RedisAuthRateLimiter
    proxy_policy: TrustedProxyPolicy
    minimum_response_seconds: float


def _required_secret(value: str | None, *, label: str) -> bytes:
    if value is None or len(value.encode()) < 32:
        raise SessionRuntimeUnavailableError(f"{label} is unavailable.")
    return value.encode()


def _proxy_policy(config: APISettings) -> TrustedProxyPolicy:
    try:
        policy = TrustedProxyPolicy.from_cidrs(
            config.auth_trusted_proxy_cidrs,
            max_forwarded_hops=config.auth_trusted_proxy_max_hops,
        )
    except ValueError as exc:
        raise SessionRuntimeUnavailableError("Trusted proxy policy is invalid.") from exc
    if any(network.prefixlen == 0 for network in policy.networks):
        raise SessionRuntimeUnavailableError("Wildcard trusted proxy networks are forbidden.")
    return policy


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return PasswordService().hash_password("pmk-dummy-login-principal")


async def build_session_runtime(config: APISettings = settings) -> SessionRuntime:
    redis = await get_redis()
    if redis is None:
        raise SessionRuntimeUnavailableError("Redis rate-limit authority is unavailable.")
    try:
        session_factory = get_session_factory()
        token_pepper = _required_secret(config.auth_token_pepper, label="Token pepper")
        rate_limit_pepper = _required_secret(
            config.auth_rate_limit_pepper,
            label="Rate-limit pepper",
        )
        minimum_response_seconds = config.auth_login_min_response_ms / 1000
        if minimum_response_seconds < 0 or minimum_response_seconds > 5:
            raise ValueError("Login response floor is outside its safe range.")
        password_service = PasswordService()
        access_token_seconds = config.auth_access_token_seconds
        refresh_token_ttl = timedelta(days=config.auth_refresh_token_days)
        failed_login_limit = config.auth_failed_login_limit
        lockout_duration = timedelta(seconds=config.auth_login_lockout_seconds)
        if access_token_seconds < 60 or access_token_seconds > 60 * 60:
            raise ValueError("Access-token lifetime is outside its safe range.")
        if refresh_token_ttl < timedelta(hours=1) or refresh_token_ttl > timedelta(days=90):
            raise ValueError("Refresh-token lifetime is outside its safe range.")
        if failed_login_limit < 2 or failed_login_limit > 20:
            raise ValueError("Failed-login limit is outside its safe range.")
        if lockout_duration < timedelta(minutes=1) or lockout_duration > timedelta(days=1):
            raise ValueError("Login lockout duration is outside its safe range.")
        proxy_policy = _proxy_policy(config)
        dummy_password_hash = _dummy_password_hash()
    except SessionRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise SessionRuntimeUnavailableError("Session authority is unavailable.") from exc

    def unit_of_work_factory() -> SqlAlchemySessionUnitOfWork:
        return SqlAlchemySessionUnitOfWork(session_factory)

    return SessionRuntime(
        service=SessionService(
            unit_of_work_factory=unit_of_work_factory,
            password_service=password_service,
            token_digester=TokenDigester(token_pepper),
            dummy_password_hash=dummy_password_hash,
            access_token_seconds=access_token_seconds,
            refresh_token_ttl=refresh_token_ttl,
            failed_login_limit=failed_login_limit,
            lockout_duration=lockout_duration,
        ),
        rate_limiter=RedisAuthRateLimiter(redis, pepper=rate_limit_pepper),
        proxy_policy=proxy_policy,
        minimum_response_seconds=minimum_response_seconds,
    )


__all__ = [
    "SessionRuntime",
    "SessionRuntimeUnavailableError",
    "build_session_runtime",
]
