from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import timedelta

from processual_api.auth.mfa_crypto import MfaSecretCipher
from processual_api.auth.mfa_repository import SqlAlchemyMfaUnitOfWork
from processual_api.auth.mfa_service import MfaService
from processual_api.auth.rate_limit import RedisAuthRateLimiter, TrustedProxyPolicy
from processual_api.auth.token_material import TokenDigester
from processual_api.cache.redis import get_redis
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class MfaRuntimeUnavailableError(RuntimeError):
    """A required MFA crypto, persistence, or rate-limit authority is unavailable."""


@dataclass(frozen=True, slots=True)
class MfaRuntime:
    service: MfaService
    rate_limiter: RedisAuthRateLimiter
    proxy_policy: TrustedProxyPolicy


def _keys(raw_json: str | None) -> dict[str, bytes]:
    if raw_json is None:
        raise MfaRuntimeUnavailableError("MFA key authority is unavailable.")
    try:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict) or not payload:
            raise ValueError
        keys = {
            str(version): base64.b64decode(encoded, validate=True)
            for version, encoded in payload.items()
            if isinstance(version, str) and isinstance(encoded, str)
        }
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise MfaRuntimeUnavailableError("MFA key authority is invalid.") from exc
    if len(keys) != len(payload):
        raise MfaRuntimeUnavailableError("MFA key authority is invalid.")
    return keys


def _required_secret(value: str | None, *, label: str) -> bytes:
    if value is None or len(value.encode()) < 32:
        raise MfaRuntimeUnavailableError(f"{label} is unavailable.")
    return value.encode()


async def build_mfa_runtime(config: APISettings = settings) -> MfaRuntime:
    redis = await get_redis()
    if redis is None:
        raise MfaRuntimeUnavailableError("MFA rate-limit authority is unavailable.")
    try:
        session_factory = get_session_factory()
        cipher = MfaSecretCipher(
            current_key_version=config.auth_mfa_current_key_version or "",
            keys=_keys(config.auth_mfa_key_ring_json),
        )
        token_pepper = _required_secret(config.auth_token_pepper, label="Token pepper")
        rate_limit_pepper = _required_secret(
            config.auth_rate_limit_pepper,
            label="Rate-limit pepper",
        )
        proxy_policy = TrustedProxyPolicy.from_cidrs(
            config.auth_trusted_proxy_cidrs,
            max_forwarded_hops=config.auth_trusted_proxy_max_hops,
        )
        if any(network.prefixlen == 0 for network in proxy_policy.networks):
            raise ValueError("Wildcard trusted proxy networks are forbidden.")
        recovery_count = config.auth_mfa_recovery_code_count
        step_up_ttl = timedelta(seconds=config.auth_mfa_step_up_seconds)
        if recovery_count < 6 or recovery_count > 20:
            raise ValueError("Invalid MFA recovery-code policy.")
        if step_up_ttl < timedelta(minutes=1) or step_up_ttl > timedelta(minutes=30):
            raise ValueError("Invalid MFA step-up lifetime.")
    except MfaRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise MfaRuntimeUnavailableError("MFA authority is unavailable.") from exc

    def unit_of_work_factory() -> SqlAlchemyMfaUnitOfWork:
        return SqlAlchemyMfaUnitOfWork(session_factory)

    return MfaRuntime(
        service=MfaService(
            unit_of_work_factory=unit_of_work_factory,
            cipher=cipher,
            token_digester=TokenDigester(token_pepper),
            issuer=config.auth_mfa_issuer,
            recovery_code_count=recovery_count,
            step_up_ttl=step_up_ttl,
        ),
        rate_limiter=RedisAuthRateLimiter(redis, pepper=rate_limit_pepper),
        proxy_policy=proxy_policy,
    )


__all__ = ["MfaRuntime", "MfaRuntimeUnavailableError", "build_mfa_runtime"]
