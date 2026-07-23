from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlencode

from processual_api.auth.delivery_contracts import (
    DeliveryClaim,
)
from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)
from processual_api.auth.delivery_provider import (
    DeliveryProvider,
    DeliveryProviderError,
    validate_https_endpoint,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeliveryEventProfile:
    purpose: str
    template: str
    verification_path: str
    eligible_user_statuses: frozenset[str]


DELIVERY_EVENT_PROFILES = {
    "verify_email": DeliveryEventProfile(
        purpose="verify_email",
        template="verify_email",
        verification_path="/verify-email",
        eligible_user_statuses=frozenset(
            {"pending_verification"}
        ),
    ),
    "verify_recovery_email": DeliveryEventProfile(
        purpose="verify_recovery_email",
        template="verify_recovery_email",
        verification_path="/auth/recovery-email/verify",
        eligible_user_statuses=frozenset({"active"}),
    ),
}


class DeliveryRepository(Protocol):
    async def claim_batch(
        self,
        *,
        now: datetime,
        lease_timeout: timedelta,
        batch_size: int,
    ) -> tuple[DeliveryClaim, ...]: ...

    async def mark_delivered(
        self,
        *,
        outbox_id: uuid.UUID,
        claim_id: uuid.UUID,
        delivered_at: datetime,
    ) -> bool: ...

    async def mark_failed(
        self,
        *,
        outbox_id: uuid.UUID,
        claim_id: uuid.UUID,
        available_at: datetime,
        error_code: str,
        dead_lettered_at: datetime | None,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeliveryDispatcherConfig:
    public_base_url: str
    batch_size: int = 25
    lease_timeout: timedelta = timedelta(minutes=5)
    max_attempts: int = 8
    retry_base: timedelta = timedelta(seconds=30)
    retry_max: timedelta = timedelta(hours=1)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "public_base_url",
            validate_https_endpoint(
                self.public_base_url,
                label="Public authentication base URL",
            ),
        )

        if self.batch_size < 1 or self.batch_size > 500:
            raise ValueError(
                "Delivery batch size is outside its safe range."
            )

        if (
            self.lease_timeout < timedelta(seconds=30)
            or self.lease_timeout > timedelta(hours=1)
        ):
            raise ValueError(
                "Delivery lease timeout is outside "
                "its safe range."
            )

        if self.max_attempts < 1 or self.max_attempts > 25:
            raise ValueError(
                "Delivery maximum attempts is outside "
                "its safe range."
            )

        if (
            self.retry_base < timedelta(seconds=1)
            or self.retry_max < self.retry_base
        ):
            raise ValueError(
                "Delivery retry policy is invalid."
            )

        if self.retry_max > timedelta(days=1):
            raise ValueError(
                "Delivery retry maximum is outside "
                "its safe range."
            )


@dataclass(frozen=True, slots=True)
class DeliveryDispatchResult:
    claimed: int = 0
    delivered: int = 0
    retry_scheduled: int = 0
    dead_lettered: int = 0
    stale_finalization: int = 0


class DeliveryDispatcher:
    def __init__(
        self,
        *,
        repository: DeliveryRepository,
        provider: DeliveryProvider,
        cipher: DeliveryPayloadCipher,
        config: DeliveryDispatcherConfig,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cipher = cipher
        self._config = config
        self._clock = clock or (
            lambda: datetime.now(UTC)
        )

    def _now(self) -> datetime:
        now = self._clock()

        if now.tzinfo is None:
            raise ValueError(
                "Delivery dispatcher clock must be "
                "timezone-aware."
            )

        return now

    def _retry_delay(
        self,
        claim: DeliveryClaim,
    ) -> timedelta:
        exponent = min(
            max(0, claim.attempt_count - 1),
            30,
        )
        base_seconds = min(
            self._config.retry_max.total_seconds(),
            self._config.retry_base.total_seconds()
            * (2**exponent),
        )
        material = (
            f"{claim.outbox_id}:{claim.attempt_count}"
        ).encode()
        fraction = (
            int.from_bytes(
                hashlib.sha256(material).digest()[:2]
            )
            / 65535
        )
        jittered = (
            base_seconds
            + base_seconds * 0.25 * fraction
        )

        return timedelta(
            seconds=min(
                jittered,
                self._config.retry_max.total_seconds(),
            )
        )

    def _verification_url(
        self,
        *,
        raw_token: str,
        profile: DeliveryEventProfile,
    ) -> str:
        query = urlencode({"token": raw_token})

        return (
            f"{self._config.public_base_url}"
            f"{profile.verification_path}?{query}"
        )

    @staticmethod
    def _idempotency_key(
        claim: DeliveryClaim,
    ) -> str:
        return (
            "pmk-auth-delivery-v1:"
            f"{claim.outbox_id}"
        )

    @staticmethod
    def _ineligible_error(
        claim: DeliveryClaim,
        now: datetime,
    ) -> str | None:
        profile = DELIVERY_EVENT_PROFILES.get(
            claim.event_type
        )

        if profile is None:
            return "event_type_invalid"

        if claim.recipient_email is None:
            return "recipient_unavailable"

        if (
            claim.user_status
            not in profile.eligible_user_statuses
        ):
            return "user_ineligible"

        if claim.action_token_consumed_at is not None:
            return "action_token_consumed"

        if claim.action_token_invalidated_at is not None:
            return "action_token_invalidated"

        if claim.action_token_expires_at <= now:
            return "action_token_expired"

        return None

    async def _fail(
        self,
        claim: DeliveryClaim,
        *,
        error_code: str,
        terminal: bool,
    ) -> tuple[int, int, int]:
        now = self._now()
        dead_lettered_at = (
            now
            if (
                terminal
                or claim.attempt_count
                >= self._config.max_attempts
            )
            else None
        )
        available_at = (
            now
            if dead_lettered_at is not None
            else now + self._retry_delay(claim)
        )

        finalized = await self._repository.mark_failed(
            outbox_id=claim.outbox_id,
            claim_id=claim.claim_id,
            available_at=available_at,
            error_code=error_code,
            dead_lettered_at=dead_lettered_at,
        )

        if not finalized:
            return (0, 0, 1)

        if dead_lettered_at is not None:
            return (0, 1, 0)

        return (1, 0, 0)

    async def dispatch_once(
        self,
    ) -> DeliveryDispatchResult:
        claims = await self._repository.claim_batch(
            now=self._now(),
            lease_timeout=self._config.lease_timeout,
            batch_size=self._config.batch_size,
        )

        delivered = 0
        retry_scheduled = 0
        dead_lettered = 0
        stale_finalization = 0

        for claim in claims:
            now = self._now()
            ineligible_error = self._ineligible_error(
                claim,
                now,
            )

            if ineligible_error is not None:
                retry, dead, stale = await self._fail(
                    claim,
                    error_code=ineligible_error,
                    terminal=True,
                )
                retry_scheduled += retry
                dead_lettered += dead
                stale_finalization += stale
                continue

            profile = DELIVERY_EVENT_PROFILES[
                claim.event_type
            ]

            try:
                raw_token = self._cipher.decrypt(
                    EncryptedDeliveryPayload(
                        ciphertext=(
                            claim.payload_ciphertext
                        ),
                        key_version=(
                            claim.payload_key_version
                        ),
                    ),
                    outbox_id=str(claim.outbox_id),
                    user_id=str(claim.user_id),
                    action_token_id=str(
                        claim.action_token_id
                    ),
                    purpose=profile.purpose,
                )

                await self._provider.send_verification_email(
                    template=profile.template,
                    recipient=claim.recipient_email,
                    verification_url=(
                        self._verification_url(
                            raw_token=raw_token,
                            profile=profile,
                        )
                    ),
                    idempotency_key=(
                        self._idempotency_key(claim)
                    ),
                )
            except DeliveryProviderError as exc:
                retry, dead, stale = await self._fail(
                    claim,
                    error_code=exc.error_code,
                    terminal=False,
                )
                retry_scheduled += retry
                dead_lettered += dead
                stale_finalization += stale
                continue
            except ValueError:
                retry, dead, stale = await self._fail(
                    claim,
                    error_code="payload_invalid",
                    terminal=False,
                )
                retry_scheduled += retry
                dead_lettered += dead
                stale_finalization += stale
                continue

            finalized = (
                await self._repository.mark_delivered(
                    outbox_id=claim.outbox_id,
                    claim_id=claim.claim_id,
                    delivered_at=self._now(),
                )
            )

            if finalized:
                delivered += 1
            else:
                stale_finalization += 1

        result = DeliveryDispatchResult(
            claimed=len(claims),
            delivered=delivered,
            retry_scheduled=retry_scheduled,
            dead_lettered=dead_lettered,
            stale_finalization=stale_finalization,
        )

        logger.info(
            "identity_delivery_dispatch_completed",
            extra={
                "claimed": result.claimed,
                "delivered": result.delivered,
                "retry_scheduled": (
                    result.retry_scheduled
                ),
                "dead_lettered": (
                    result.dead_lettered
                ),
                "stale_finalization": (
                    result.stale_finalization
                ),
            },
        )

        return result


__all__ = [
    "DELIVERY_EVENT_PROFILES",
    "DeliveryDispatchResult",
    "DeliveryDispatcher",
    "DeliveryDispatcherConfig",
    "DeliveryEventProfile",
]
