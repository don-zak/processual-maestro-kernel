from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)
from processual_api.auth.rate_limit import (
    RedisAuthRateLimiter,
    TrustedProxyPolicy,
)
from processual_api.auth.recovery_email_verification_repository import (
    SqlAlchemyRecoveryEmailVerificationUnitOfWork,
)
from processual_api.auth.recovery_email_verification_service import (
    RecoveryEmailVerificationService,
)
from processual_api.auth.token_material import TokenDigester
from processual_api.cache.redis import get_redis
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings

MINIMUM_SECRET_BYTES = 32


class RecoveryEmailRuntimeUnavailableError(RuntimeError):
    """Recovery-email runtime authority is unavailable."""


@dataclass(frozen=True, slots=True)
class RecoveryEmailRuntime:
    service: RecoveryEmailVerificationService
    rate_limiter: RedisAuthRateLimiter
    proxy_policy: TrustedProxyPolicy
    minimum_response_seconds: float


def _required_secret(
    value: str | None,
    *,
    label: str,
) -> bytes:
    raw = (value or "").encode()

    if len(raw) < MINIMUM_SECRET_BYTES:
        raise RecoveryEmailRuntimeUnavailableError(
            f"{label} is unavailable."
        )

    return raw


def _delivery_keys(
    raw_json: str | None,
) -> dict[str, bytes]:
    if raw_json is None:
        raise RecoveryEmailRuntimeUnavailableError(
            "Delivery key authority is unavailable."
        )

    try:
        payload = json.loads(raw_json)

        if not isinstance(payload, dict) or not payload:
            raise ValueError

        keys = {
            str(version): base64.b64decode(
                encoded,
                validate=True,
            )
            for version, encoded in payload.items()
            if (
                isinstance(version, str)
                and isinstance(encoded, str)
            )
        }
    except (
        ValueError,
        TypeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise RecoveryEmailRuntimeUnavailableError(
            "Delivery key authority is invalid."
        ) from exc

    if len(keys) != len(payload):
        raise RecoveryEmailRuntimeUnavailableError(
            "Delivery key authority is invalid."
        )

    return keys


def _proxy_policy(
    config: APISettings,
) -> TrustedProxyPolicy:
    try:
        policy = TrustedProxyPolicy.from_cidrs(
            config.auth_trusted_proxy_cidrs,
            max_forwarded_hops=(
                config.auth_trusted_proxy_max_hops
            ),
        )
    except ValueError as exc:
        raise RecoveryEmailRuntimeUnavailableError(
            "Trusted proxy policy is invalid."
        ) from exc

    if any(
        network.prefixlen == 0
        for network in policy.networks
    ):
        raise RecoveryEmailRuntimeUnavailableError(
            "Wildcard trusted proxy networks are forbidden."
        )

    return policy


async def build_recovery_email_runtime(
    config: APISettings = settings,
) -> RecoveryEmailRuntime:
    redis = await get_redis()

    if redis is None:
        raise RecoveryEmailRuntimeUnavailableError(
            "Redis rate-limit authority is unavailable."
        )

    try:
        session_factory = get_session_factory()
        token_pepper = _required_secret(
            config.auth_token_pepper,
            label="Token pepper",
        )
        rate_limit_pepper = _required_secret(
            config.auth_rate_limit_pepper,
            label="Rate-limit pepper",
        )
        cipher = DeliveryPayloadCipher(
            current_key_version=(
                config.auth_delivery_current_key_version
                or ""
            ),
            keys=_delivery_keys(
                config.auth_delivery_key_ring_json
            ),
        )
        minimum_response_seconds = (
            config.auth_registration_min_response_ms
            / 1000
        )

        if (
            minimum_response_seconds < 0
            or minimum_response_seconds > 5
        ):
            raise ValueError(
                "Recovery-email response floor "
                "is outside its safe range."
            )

        proxy_policy = _proxy_policy(config)
    except RecoveryEmailRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise RecoveryEmailRuntimeUnavailableError(
            "Recovery-email authority is unavailable."
        ) from exc

    def unit_of_work_factory():
        return SqlAlchemyRecoveryEmailVerificationUnitOfWork(
            session_factory
        )

    return RecoveryEmailRuntime(
        service=RecoveryEmailVerificationService(
            unit_of_work_factory=unit_of_work_factory,
            token_digester=TokenDigester(token_pepper),
            delivery_cipher=cipher,
        ),
        rate_limiter=RedisAuthRateLimiter(
            redis,
            pepper=rate_limit_pepper,
        ),
        proxy_policy=proxy_policy,
        minimum_response_seconds=minimum_response_seconds,
    )


__all__ = [
    "RecoveryEmailRuntime",
    "RecoveryEmailRuntimeUnavailableError",
    "build_recovery_email_runtime",
]
