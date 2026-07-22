from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.email_verification_service import EmailVerificationService
from processual_api.auth.passwords import PasswordService
from processual_api.auth.rate_limit import RedisAuthRateLimiter, TrustedProxyPolicy
from processual_api.auth.registration_repository import SqlAlchemyRegistrationUnitOfWork
from processual_api.auth.registration_service import RegistrationService
from processual_api.auth.token_material import TokenDigester
from processual_api.cache.redis import get_redis
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class RegistrationRuntimeUnavailableError(RuntimeError):
    """A required registration authority is missing or invalid."""


@dataclass(frozen=True, slots=True)
class RegistrationRuntime:
    service: RegistrationService
    rate_limiter: RedisAuthRateLimiter
    proxy_policy: TrustedProxyPolicy
    minimum_response_seconds: float
    email_verification_service: EmailVerificationService | None = None


def _required_secret(value: str | None, *, label: str) -> bytes:
    if value is None or len(value.encode()) < 32:
        raise RegistrationRuntimeUnavailableError(f"{label} is unavailable.")
    return value.encode()


def _delivery_keys(raw_json: str | None) -> dict[str, bytes]:
    if raw_json is None:
        raise RegistrationRuntimeUnavailableError("Delivery key authority is unavailable.")
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
        raise RegistrationRuntimeUnavailableError("Delivery key authority is invalid.") from exc
    if len(keys) != len(payload):
        raise RegistrationRuntimeUnavailableError("Delivery key authority is invalid.")
    return keys


def _proxy_policy(config: APISettings) -> TrustedProxyPolicy:
    try:
        policy = TrustedProxyPolicy.from_cidrs(
            config.auth_trusted_proxy_cidrs,
            max_forwarded_hops=config.auth_trusted_proxy_max_hops,
        )
    except ValueError as exc:
        raise RegistrationRuntimeUnavailableError("Trusted proxy policy is invalid.") from exc
    if any(network.prefixlen == 0 for network in policy.networks):
        raise RegistrationRuntimeUnavailableError("Wildcard trusted proxy networks are forbidden.")
    return policy


async def build_registration_runtime(config: APISettings = settings) -> RegistrationRuntime:
    redis = await get_redis()
    if redis is None:
        raise RegistrationRuntimeUnavailableError("Redis rate-limit authority is unavailable.")
    try:
        session_factory = get_session_factory()
        token_pepper = _required_secret(config.auth_token_pepper, label="Token pepper")
        rate_limit_pepper = _required_secret(
            config.auth_rate_limit_pepper,
            label="Rate-limit pepper",
        )
        delivery_cipher = DeliveryPayloadCipher(
            current_key_version=config.auth_delivery_current_key_version or "",
            keys=_delivery_keys(config.auth_delivery_key_ring_json),
        )
        minimum_response_seconds = config.auth_registration_min_response_ms / 1000
        if minimum_response_seconds < 0 or minimum_response_seconds > 5:
            raise ValueError("Registration response floor is outside its safe range.")
    except RegistrationRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise RegistrationRuntimeUnavailableError("Registration authority is unavailable.") from exc

    def unit_of_work_factory() -> SqlAlchemyRegistrationUnitOfWork:
        return SqlAlchemyRegistrationUnitOfWork(session_factory)
    token_digester = TokenDigester(token_pepper)
    return RegistrationRuntime(
        service=RegistrationService(
            unit_of_work_factory=unit_of_work_factory,
            password_service=PasswordService(),
            token_digester=token_digester,
            delivery_cipher=delivery_cipher,
        ),
        email_verification_service=EmailVerificationService(
            unit_of_work_factory=unit_of_work_factory,
            token_digester=token_digester,
            delivery_cipher=delivery_cipher,
        ),
        rate_limiter=RedisAuthRateLimiter(redis, pepper=rate_limit_pepper),
        proxy_policy=_proxy_policy(config),
        minimum_response_seconds=minimum_response_seconds,
    )


__all__ = [
    "RegistrationRuntime",
    "RegistrationRuntimeUnavailableError",
    "build_registration_runtime",
]
