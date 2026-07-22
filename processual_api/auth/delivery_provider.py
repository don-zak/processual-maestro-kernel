from __future__ import annotations

from typing import Protocol
from urllib.parse import urlsplit

import httpx


class DeliveryProviderError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        super().__init__("Delivery provider request failed.")
        self.error_code = error_code


class DeliveryProvider(Protocol):
    async def send_verification_email(
        self,
        *,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None: ...


def validate_https_endpoint(value: str, *, label: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be an HTTPS URL without credentials, query, or fragment.")
    return normalized


class HttpEmailDeliveryProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        bearer_token: str,
        timeout_seconds: float,
    ) -> None:
        self._endpoint = validate_https_endpoint(endpoint, label="Delivery provider URL")
        if len(bearer_token.encode()) < 32:
            raise ValueError("Delivery provider token must contain at least 32 bytes.")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("Delivery provider timeout is outside its safe range.")
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds

    async def send_verification_email(
        self,
        *,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._bearer_token}",
                        "Idempotency-Key": idempotency_key,
                    },
                    json={
                        "template": "verify_email",
                        "recipient": recipient,
                        "verification_url": verification_url,
                    },
                )
        except httpx.TimeoutException as exc:
            raise DeliveryProviderError("provider_timeout") from exc
        except httpx.RequestError as exc:
            raise DeliveryProviderError("provider_network") from exc
        if 200 <= response.status_code < 300:
            return
        if response.status_code >= 500:
            raise DeliveryProviderError("provider_5xx")
        raise DeliveryProviderError("provider_4xx")


__all__ = [
    "DeliveryProvider",
    "DeliveryProviderError",
    "HttpEmailDeliveryProvider",
    "validate_https_endpoint",
]
