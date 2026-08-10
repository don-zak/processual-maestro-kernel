from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.models import AdminMarketNotificationOutbox

_EVENT_TYPES = frozenset(
    {
        "order_created",
        "contract_completed",
        "payment_instructions_ready",
        "payment_reported",
        "payment_verified",
        "payment_requires_review",
        "subscription_activated",
        "activation_failed",
        "order_cancelled",
    }
)
_PROHIBITED_PAYLOAD_KEY = re.compile(
    r"(?:account|iban|rib|identifier|cipher|secret|token|password|credential|evidence_raw|transfer_reference)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CommercialNotificationClaim:
    outbox_id: uuid.UUID
    claim_id: uuid.UUID
    event_ref: str
    event_type: str
    aggregate_type: str
    aggregate_ref: str
    recipient_customer_ref: str
    payload: Mapping[str, str]
    attempt_count: int


@dataclass(frozen=True, slots=True)
class CommercialNotificationDispatchResult:
    claimed: int
    delivered: int
    retry_scheduled: int
    dead_lettered: int


class CommercialNotificationAdapter(Protocol):
    async def deliver(self, claim: CommercialNotificationClaim) -> None: ...


class SqlAlchemyNotificationOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, event: AdminMarketNotificationOutbox) -> None:
        self._session.add(event)

    async def list_recent(self, *, limit: int = 100) -> tuple[AdminMarketNotificationOutbox, ...]:
        result = await self._session.scalars(
            select(AdminMarketNotificationOutbox)
            .order_by(AdminMarketNotificationOutbox.created_at.desc(), AdminMarketNotificationOutbox.id.desc())
            .limit(limit)
        )
        return tuple(result.all())

    async def get_by_deduplication_key_hash(self, key_hash: str) -> AdminMarketNotificationOutbox | None:
        return await self._session.scalar(
            select(AdminMarketNotificationOutbox).where(
                AdminMarketNotificationOutbox.deduplication_key_hash == key_hash
            )
        )


class SqlAlchemyNotificationDeliveryRepository:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def claim_batch(
        self, *, now: datetime, lease_timeout: timedelta, batch_size: int
    ) -> tuple[CommercialNotificationClaim, ...]:
        _aware(now)
        if batch_size < 1 or batch_size > 500:
            raise ValueError("Notification batch_size is invalid.")
        stale_before = now - lease_timeout
        async with self._session_factory() as session:
            async with session.begin():
                statement = (
                    select(AdminMarketNotificationOutbox)
                    .where(
                        AdminMarketNotificationOutbox.delivered_at.is_(None),
                        AdminMarketNotificationOutbox.dead_lettered_at.is_(None),
                        AdminMarketNotificationOutbox.available_at <= now,
                        or_(
                            AdminMarketNotificationOutbox.claimed_at.is_(None),
                            AdminMarketNotificationOutbox.claimed_at <= stale_before,
                        ),
                    )
                    .order_by(AdminMarketNotificationOutbox.available_at, AdminMarketNotificationOutbox.created_at)
                    .limit(batch_size)
                    .with_for_update(of=AdminMarketNotificationOutbox, skip_locked=True)
                )
                rows = tuple((await session.scalars(statement)).all())
                claims = []
                for row in rows:
                    claim_id = uuid.uuid4()
                    row.claim_id = claim_id
                    row.claimed_at = now
                    row.attempt_count += 1
                    claims.append(
                        CommercialNotificationClaim(
                            outbox_id=row.id,
                            claim_id=claim_id,
                            event_ref=row.event_ref,
                            event_type=row.event_type,
                            aggregate_type=row.aggregate_type,
                            aggregate_ref=row.aggregate_ref,
                            recipient_customer_ref=row.recipient_customer_ref,
                            payload=dict(row.payload_json),
                            attempt_count=row.attempt_count,
                        )
                    )
        return tuple(claims)

    async def mark_delivered(self, *, outbox_id: uuid.UUID, claim_id: uuid.UUID, delivered_at: datetime) -> bool:
        _aware(delivered_at)
        return await self._finalize(
            outbox_id=outbox_id,
            claim_id=claim_id,
            values={
                "delivered_at": delivered_at,
                "claim_id": None,
                "claimed_at": None,
                "last_error_code": None,
            },
        )

    async def mark_failed(
        self,
        *,
        outbox_id: uuid.UUID,
        claim_id: uuid.UUID,
        available_at: datetime,
        error_code: str,
        dead_lettered_at: datetime | None,
    ) -> bool:
        _aware(available_at)
        if dead_lettered_at is not None:
            _aware(dead_lettered_at)
        normalized_error = error_code.strip().lower()
        if not normalized_error or len(normalized_error) > 80:
            raise ValueError("Notification error_code is invalid.")
        return await self._finalize(
            outbox_id=outbox_id,
            claim_id=claim_id,
            values={
                "available_at": available_at,
                "claim_id": None,
                "claimed_at": None,
                "last_error_code": normalized_error,
                "dead_lettered_at": dead_lettered_at,
            },
        )

    async def _finalize(self, *, outbox_id, claim_id, values) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    update(AdminMarketNotificationOutbox)
                    .where(
                        AdminMarketNotificationOutbox.id == outbox_id,
                        AdminMarketNotificationOutbox.claim_id == claim_id,
                        AdminMarketNotificationOutbox.delivered_at.is_(None),
                        AdminMarketNotificationOutbox.dead_lettered_at.is_(None),
                    )
                    .values(**values)
                )
        return result.rowcount == 1


class CommercialNotificationDispatcher:
    def __init__(
        self,
        *,
        repository: SqlAlchemyNotificationDeliveryRepository,
        adapter: CommercialNotificationAdapter,
        clock: Callable[[], datetime],
        max_attempts: int = 5,
    ) -> None:
        self._repository, self._adapter, self._clock, self._max_attempts = repository, adapter, clock, max_attempts

    async def dispatch_once(self, *, batch_size: int = 50) -> CommercialNotificationDispatchResult:
        now = self._clock()
        claims = await self._repository.claim_batch(now=now, lease_timeout=timedelta(minutes=5), batch_size=batch_size)
        delivered = retry_scheduled = dead_lettered = 0
        for claim in claims:
            try:
                await self._adapter.deliver(claim)
            except Exception:
                is_dead = claim.attempt_count >= self._max_attempts
                await self._repository.mark_failed(
                    outbox_id=claim.outbox_id,
                    claim_id=claim.claim_id,
                    available_at=now + _retry_delay(claim.attempt_count),
                    error_code="notification_delivery_failed",
                    dead_lettered_at=now if is_dead else None,
                )
                dead_lettered += int(is_dead)
                retry_scheduled += int(not is_dead)
            else:
                await self._repository.mark_delivered(
                    outbox_id=claim.outbox_id, claim_id=claim.claim_id, delivered_at=now
                )
                delivered += 1
        return CommercialNotificationDispatchResult(len(claims), delivered, retry_scheduled, dead_lettered)


def enqueue_commercial_notification(
    unit,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_ref: str,
    customer_ref: str,
    payload: Mapping[str, str],
    deduplication_material: str,
    occurred_at: datetime,
    id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
) -> AdminMarketNotificationOutbox | None:
    repository = getattr(unit, "notification_outbox", None)
    if repository is None:
        return None
    normalized_payload = _safe_payload(payload)
    if event_type not in _EVENT_TYPES:
        raise ValueError("Commercial notification event_type is invalid.")
    _aware(occurred_at)
    event_id = id_factory()
    event = AdminMarketNotificationOutbox(
        id=event_id,
        event_ref=f"cno_{event_id.hex[:24]}",
        event_type=event_type,
        aggregate_type=_required(aggregate_type, "aggregate_type", 32),
        aggregate_ref=_required(aggregate_ref, "aggregate_ref", 128),
        recipient_customer_ref=_required(customer_ref, "customer_ref", 128),
        payload_json=normalized_payload,
        deduplication_key_hash=_sha256(
            f"{event_type}:{aggregate_ref}:{_required(deduplication_material, 'deduplication_material', 256)}"
        ),
        available_at=occurred_at,
        attempt_count=0,
        claim_id=None,
        claimed_at=None,
        delivered_at=None,
        dead_lettered_at=None,
        last_error_code=None,
        created_at=occurred_at,
    )
    repository.add(event)
    return event


def _safe_payload(payload: Mapping[str, str]) -> dict[str, str]:
    if len(payload) > 12:
        raise ValueError("Commercial notification payload is too large.")
    result = {}
    for key, value in payload.items():
        normalized_key = _required(str(key), "payload key", 64)
        if _PROHIBITED_PAYLOAD_KEY.search(normalized_key):
            raise ValueError("Sensitive notification payload key is forbidden.")
        result[normalized_key] = _required(str(value), "payload value", 256)
    return result


def _required(value: str, name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{name} is invalid.")
    return normalized


def _aware(value: datetime) -> None:
    if value.tzinfo is None:
        raise ValueError("Commercial notification time must be timezone-aware.")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _retry_delay(attempt_count: int) -> timedelta:
    return timedelta(seconds=min(3600, 30 * (2 ** max(0, attempt_count - 1))))


__all__: Sequence[str] = (
    "CommercialNotificationAdapter",
    "CommercialNotificationClaim",
    "CommercialNotificationDispatchResult",
    "CommercialNotificationDispatcher",
    "SqlAlchemyNotificationDeliveryRepository",
    "SqlAlchemyNotificationOutboxRepository",
    "enqueue_commercial_notification",
)
