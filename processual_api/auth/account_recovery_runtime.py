from __future__ import annotations

import base64
import binascii
import importlib
import json
from dataclasses import dataclass

from processual_api.auth.account_recovery_external_revocation import (
    AccountRecoveryExternalAuthorityRevoker,
)
from processual_api.auth.account_recovery_repository import (
    SqlAlchemyAccountRecoveryUnitOfWork,
)
from processual_api.auth.account_recovery_service import (
    AccountRecoveryService,
)
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)
from processual_api.auth.rate_limit import (
    RedisAuthRateLimiter,
    TrustedProxyPolicy,
)
from processual_api.auth.token_material import (
    TokenDigester,
)
from processual_api.cache.redis import get_redis
from processual_api.db.session import (
    get_session_factory,
)
from processual_api.settings import APISettings, settings

MINIMUM_SECRET_BYTES = 32


class AccountRecoveryRuntimeUnavailableError(RuntimeError):
    """Account-recovery runtime authority is unavailable."""


@dataclass(frozen=True, slots=True)
class AccountRecoveryRuntime:
    service: AccountRecoveryService
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
        raise AccountRecoveryRuntimeUnavailableError(f"{label} is unavailable.")

    return raw


def _delivery_keys(
    raw_json: str | None,
) -> dict[str, bytes]:
    if raw_json is None:
        raise AccountRecoveryRuntimeUnavailableError("Delivery key authority is unavailable.")

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
            if (isinstance(version, str) and isinstance(encoded, str))
        }
    except (
        ValueError,
        TypeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise AccountRecoveryRuntimeUnavailableError("Delivery key authority is invalid.") from exc

    if len(keys) != len(payload):
        raise AccountRecoveryRuntimeUnavailableError("Delivery key authority is invalid.")

    return keys


def _proxy_policy(
    config: APISettings,
) -> TrustedProxyPolicy:
    try:
        policy = TrustedProxyPolicy.from_cidrs(
            config.auth_trusted_proxy_cidrs,
            max_forwarded_hops=(config.auth_trusted_proxy_max_hops),
        )
    except ValueError as exc:
        raise AccountRecoveryRuntimeUnavailableError("Trusted proxy policy is invalid.") from exc

    if any(network.prefixlen == 0 for network in policy.networks):
        raise AccountRecoveryRuntimeUnavailableError("Wildcard trusted proxy networks are forbidden.")

    return policy


def _build_external_authority_revoker() -> AccountRecoveryExternalAuthorityRevoker:
    try:
        settings_module = importlib.import_module("processual_api.routers.settings")

        supervisor_store_path = settings_module._supervisor_session_key_store_path()
        settings_loader = settings_module._load_raw
        settings_saver = settings_module._save_raw
    except (
        AttributeError,
        ImportError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise AccountRecoveryRuntimeUnavailableError("External recovery authority is unavailable.") from exc

    return AccountRecoveryExternalAuthorityRevoker(
        supervisor_store_path=supervisor_store_path,
        settings_loader=settings_loader,
        settings_saver=settings_saver,
    )


async def build_account_recovery_runtime(
    config: APISettings = settings,
) -> AccountRecoveryRuntime:
    redis = await get_redis()

    if redis is None:
        raise AccountRecoveryRuntimeUnavailableError("Redis rate-limit authority is unavailable.")

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

        delivery_cipher = DeliveryPayloadCipher(
            current_key_version=(config.auth_delivery_current_key_version or ""),
            keys=_delivery_keys(config.auth_delivery_key_ring_json),
        )

        minimum_response_seconds = config.auth_registration_min_response_ms / 1000

        if minimum_response_seconds < 0 or minimum_response_seconds > 5:
            raise ValueError("Account-recovery response floor is outside its safe range.")

        proxy_policy = _proxy_policy(config)
        external_authority_revoker = _build_external_authority_revoker()
    except AccountRecoveryRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise AccountRecoveryRuntimeUnavailableError("Account-recovery authority is unavailable.") from exc

    def unit_of_work_factory():
        return SqlAlchemyAccountRecoveryUnitOfWork(session_factory)

    return AccountRecoveryRuntime(
        service=AccountRecoveryService(
            unit_of_work_factory=unit_of_work_factory,
            token_digester=TokenDigester(token_pepper),
            delivery_cipher=delivery_cipher,
            external_authority_revoker=(external_authority_revoker),
        ),
        rate_limiter=RedisAuthRateLimiter(
            redis,
            pepper=rate_limit_pepper,
        ),
        proxy_policy=proxy_policy,
        minimum_response_seconds=(minimum_response_seconds),
    )


__all__ = [
    "AccountRecoveryRuntime",
    "AccountRecoveryRuntimeUnavailableError",
    "build_account_recovery_runtime",
]
