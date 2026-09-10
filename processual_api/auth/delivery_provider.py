from __future__ import annotations

import base64
import hashlib
from email.message import EmailMessage
from typing import Protocol
from urllib.parse import urlsplit

import httpx

ALLOWED_VERIFICATION_TEMPLATES = frozenset(
    {
        "verify_email",
        "verify_recovery_email",
        "account_recovery_verification",
    }
)

GMAIL_OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

_TEMPLATE_SUBJECTS = {
    "verify_email": "Verify your Processual Maestro email",
    "verify_recovery_email": "Verify your Processual Maestro recovery email",
    "account_recovery_verification": "Recover your Processual Maestro account",
}

_TEMPLATE_INTRO = {
    "verify_email": "Use the secure link below to verify your Processual Maestro email address.",
    "verify_recovery_email": (
        "Use the secure link below to verify your Processual Maestro recovery address."
    ),
    "account_recovery_verification": (
        "Use the secure link below to continue Processual Maestro account recovery."
    ),
}


class DeliveryProviderError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        *,
        retryable: bool = True,
    ) -> None:
        super().__init__("Delivery provider request failed.")
        self.error_code = error_code
        self.retryable = retryable


class DeliveryProvider(Protocol):
    async def send_verification_email(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None: ...


def validate_https_endpoint(
    value: str,
    *,
    label: str,
) -> str:
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


def _validate_sender_email(value: str) -> str:
    normalized = value.strip()
    if (
        len(normalized) > 320
        or normalized.count("@") != 1
        or normalized.startswith("@")
        or normalized.endswith("@")
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("Gmail sender email is unavailable.")
    return normalized


class HttpEmailDeliveryProvider:
    def __init__(
        self,
        *,
        endpoint: str,
        bearer_token: str,
        timeout_seconds: float,
    ) -> None:
        self._endpoint = validate_https_endpoint(
            endpoint,
            label="Delivery provider URL",
        )

        if len(bearer_token.encode()) < 32:
            raise ValueError("Delivery provider token must contain at least 32 bytes.")

        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("Delivery provider timeout is outside its safe range.")

        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds

    async def send_verification_email(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None:
        if template not in ALLOWED_VERIFICATION_TEMPLATES:
            raise ValueError("Delivery verification template is invalid.")

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": (f"Bearer {self._bearer_token}"),
                        "Idempotency-Key": idempotency_key,
                    },
                    json={
                        "template": template,
                        "recipient": recipient,
                        "verification_url": verification_url,
                    },
                )
        except httpx.TimeoutException as exc:
            raise DeliveryProviderError(
                "provider_timeout",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise DeliveryProviderError(
                "provider_network",
                retryable=True,
            ) from exc

        if 200 <= response.status_code < 300:
            return

        if response.status_code == 408:
            raise DeliveryProviderError(
                "provider_timeout",
                retryable=True,
            )

        if response.status_code == 429:
            raise DeliveryProviderError(
                "provider_rate_limited",
                retryable=True,
            )

        if response.status_code >= 500:
            raise DeliveryProviderError(
                "provider_5xx",
                retryable=True,
            )

        raise DeliveryProviderError(
            "provider_4xx",
            retryable=False,
        )


class GmailApiDeliveryProvider:
    """Send authentication emails through Gmail API using OAuth refresh authority."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sender_email: str,
        timeout_seconds: float,
    ) -> None:
        normalized_client_id = client_id.strip()
        normalized_client_secret = client_secret.strip()
        normalized_refresh_token = refresh_token.strip()

        if len(normalized_client_id) < 10:
            raise ValueError("Gmail OAuth client id is unavailable.")
        if len(normalized_client_secret) < 16:
            raise ValueError("Gmail OAuth client secret is unavailable.")
        if len(normalized_refresh_token) < 32:
            raise ValueError("Gmail OAuth refresh token is unavailable.")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("Delivery provider timeout is outside its safe range.")

        self._client_id = normalized_client_id
        self._client_secret = normalized_client_secret
        self._refresh_token = normalized_refresh_token
        self._sender_email = _validate_sender_email(sender_email)
        self._timeout_seconds = timeout_seconds

    def _raw_message(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> str:
        if template not in ALLOWED_VERIFICATION_TEMPLATES:
            raise ValueError("Delivery verification template is invalid.")

        message = EmailMessage()
        message["From"] = self._sender_email
        message["To"] = recipient
        message["Subject"] = _TEMPLATE_SUBJECTS[template]
        message["Auto-Submitted"] = "auto-generated"
        message["X-Auto-Response-Suppress"] = "All"
        stable_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        message["Message-ID"] = f"<{stable_digest}@delivery.processual-maestro.invalid>"
        message.set_content(
            f"{_TEMPLATE_INTRO[template]}\n\n"
            f"{verification_url}\n\n"
            "If you did not request this action, you can ignore this message."
        )
        return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")

    @staticmethod
    def _raise_for_oauth_response(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise DeliveryProviderError("provider_rate_limited", retryable=True)
        if response.status_code >= 500:
            raise DeliveryProviderError("provider_5xx", retryable=True)
        raise DeliveryProviderError("provider_oauth_rejected", retryable=False)

    @staticmethod
    def _raise_for_send_response(response: httpx.Response) -> None:
        if response.status_code == 408:
            raise DeliveryProviderError("provider_timeout", retryable=True)
        if response.status_code == 429:
            raise DeliveryProviderError("provider_rate_limited", retryable=True)
        if response.status_code >= 500:
            raise DeliveryProviderError("provider_5xx", retryable=True)
        raise DeliveryProviderError("provider_4xx", retryable=False)

    async def send_verification_email(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None:
        raw_message = self._raw_message(
            template=template,
            recipient=recipient,
            verification_url=verification_url,
            idempotency_key=idempotency_key,
        )

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                token_response = await client.post(
                    GMAIL_OAUTH_TOKEN_ENDPOINT,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "refresh_token": self._refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
                if not 200 <= token_response.status_code < 300:
                    self._raise_for_oauth_response(token_response)

                payload = token_response.json()
                access_token = str(payload.get("access_token") or "").strip()
                token_type = str(payload.get("token_type") or "Bearer").strip()
                if not access_token or token_type.casefold() != "bearer":
                    raise DeliveryProviderError(
                        "provider_oauth_rejected",
                        retryable=False,
                    )

                send_response = await client.post(
                    GMAIL_SEND_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                    json={"raw": raw_message},
                )
        except DeliveryProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise DeliveryProviderError("provider_timeout", retryable=True) from exc
        except httpx.RequestError as exc:
            raise DeliveryProviderError("provider_network", retryable=True) from exc
        except (TypeError, ValueError) as exc:
            raise DeliveryProviderError("provider_oauth_rejected", retryable=False) from exc

        if 200 <= send_response.status_code < 300:
            return

        self._raise_for_send_response(send_response)


__all__ = [
    "ALLOWED_VERIFICATION_TEMPLATES",
    "DeliveryProvider",
    "DeliveryProviderError",
    "GMAIL_OAUTH_TOKEN_ENDPOINT",
    "GMAIL_SEND_ENDPOINT",
    "GmailApiDeliveryProvider",
    "HttpEmailDeliveryProvider",
    "validate_https_endpoint",
]
