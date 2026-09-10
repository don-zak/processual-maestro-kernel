from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import timedelta

from processual_api.auth.delivery_crypto import DeliveryPayloadCipher
from processual_api.auth.delivery_dispatcher import (
    DeliveryDispatcher,
    DeliveryDispatcherConfig,
)
from processual_api.auth.delivery_provider import (
    GmailApiDeliveryProvider,
    HttpEmailDeliveryProvider,
)
from processual_api.auth.delivery_repository import SqlAlchemyDeliveryRepository
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class DeliveryRuntimeUnavailableError(RuntimeError):
    """A required delivery worker authority is missing or invalid."""


@dataclass(frozen=True, slots=True)
class DeliveryRuntime:
    dispatcher: DeliveryDispatcher


def _delivery_keys(raw_json: str | None) -> dict[str, bytes]:
    if raw_json is None:
        raise DeliveryRuntimeUnavailableError("Delivery key authority is unavailable.")
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
        raise DeliveryRuntimeUnavailableError("Delivery key authority is invalid.") from exc
    if len(keys) != len(payload):
        raise DeliveryRuntimeUnavailableError("Delivery key authority is invalid.")
    return keys


def _build_provider(config: APISettings):
    provider_kind = (config.auth_delivery_provider_kind or "http").strip().casefold()

    if provider_kind == "http":
        return HttpEmailDeliveryProvider(
            endpoint=config.auth_delivery_provider_url or "",
            bearer_token=config.auth_delivery_provider_token or "",
            timeout_seconds=config.auth_delivery_request_timeout_seconds,
        )

    if provider_kind == "gmail_api":
        return GmailApiDeliveryProvider(
            client_id=config.auth_gmail_client_id or "",
            client_secret=config.auth_gmail_client_secret or "",
            refresh_token=config.auth_gmail_refresh_token or "",
            timeout_seconds=config.auth_delivery_request_timeout_seconds,
        )

    raise DeliveryRuntimeUnavailableError("Delivery provider kind is unsupported.")


def build_delivery_runtime(config: APISettings = settings) -> DeliveryRuntime:
    try:
        session_factory = get_session_factory()
        public_base_url = config.auth_public_base_url or ""
        cipher = DeliveryPayloadCipher(
            current_key_version=config.auth_delivery_current_key_version or "",
            keys=_delivery_keys(config.auth_delivery_key_ring_json),
        )
        provider = _build_provider(config)
        dispatcher_config = DeliveryDispatcherConfig(
            public_base_url=public_base_url,
            batch_size=config.auth_delivery_batch_size,
            lease_timeout=timedelta(seconds=config.auth_delivery_lease_seconds),
            max_attempts=config.auth_delivery_max_attempts,
            retry_base=timedelta(seconds=config.auth_delivery_retry_base_seconds),
            retry_max=timedelta(seconds=config.auth_delivery_retry_max_seconds),
        )
    except DeliveryRuntimeUnavailableError:
        raise
    except (RuntimeError, ValueError) as exc:
        raise DeliveryRuntimeUnavailableError("Delivery worker authority is unavailable.") from exc
    return DeliveryRuntime(
        dispatcher=DeliveryDispatcher(
            repository=SqlAlchemyDeliveryRepository(session_factory),
            provider=provider,
            cipher=cipher,
            config=dispatcher_config,
        )
    )


__all__ = [
    "DeliveryRuntime",
    "DeliveryRuntimeUnavailableError",
    "build_delivery_runtime",
]
