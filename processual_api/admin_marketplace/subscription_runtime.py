from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal


AccessStage = Literal["active", "grace", "suspended", "terminated"]


class SubscriptionRuntimeError(ValueError):
    pass


@dataclass(slots=True)
class SubscriptionRuntimeState:
    subscription_id: object
    customer_ref: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    access_stage: AccessStage
    version: int
    effective_at: datetime
    grace_until: datetime | None = None
    suspended_at: datetime | None = None
    terminated_at: datetime | None = None


@dataclass(slots=True)
class SubscriptionQuotaAccountState:
    id: object
    subscription_id: object
    customer_ref: str
    quota_profile_ref: str
    metric_code: str
    period_start: datetime
    period_end: datetime
    limit_units: int
    used_units: int
    version: int


@dataclass(frozen=True, slots=True)
class UsageReservation:
    units: int
    idempotency_key_hash: str
    dimensions_digest: str
    occurred_at: datetime


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise SubscriptionRuntimeError(f"{field_name} must be timezone-aware.")
    return value


def transition_subscription_runtime(
    state: SubscriptionRuntimeState,
    *,
    target_stage: AccessStage,
    effective_at: datetime,
    grace_until: datetime | None = None,
) -> None:
    timestamp = _aware(effective_at, "effective_at")
    if timestamp < state.effective_at:
        raise SubscriptionRuntimeError("runtime transition cannot move backward in time.")
    allowed = {
        "active": {"active", "grace", "suspended", "terminated"},
        "grace": {"active", "suspended", "terminated"},
        "suspended": {"active", "terminated"},
        "terminated": {"terminated"},
    }
    if target_stage not in allowed[state.access_stage]:
        raise SubscriptionRuntimeError("subscription runtime transition is not allowed.")
    if target_stage == "grace":
        if grace_until is None:
            raise SubscriptionRuntimeError("grace_until is required for grace stage.")
        _aware(grace_until, "grace_until")
        if grace_until <= timestamp:
            raise SubscriptionRuntimeError("grace_until must be after effective_at.")

    state.access_stage = target_stage
    state.version += 1
    state.effective_at = timestamp
    state.grace_until = grace_until if target_stage == "grace" else None
    state.suspended_at = timestamp if target_stage == "suspended" else None
    state.terminated_at = timestamp if target_stage == "terminated" else None


def build_usage_reservation(
    *,
    units: int,
    idempotency_key: str,
    dimensions: dict[str, object],
    occurred_at: datetime | None = None,
) -> UsageReservation:
    if units <= 0:
        raise SubscriptionRuntimeError("usage units must be positive.")
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 512:
        raise SubscriptionRuntimeError("usage idempotency key is invalid.")
    timestamp = occurred_at or datetime.now(timezone.utc)
    _aware(timestamp, "occurred_at")
    try:
        canonical_dimensions = json.dumps(
            dimensions,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SubscriptionRuntimeError("usage dimensions are invalid.") from exc
    return UsageReservation(
        units=units,
        idempotency_key_hash=sha256(normalized_key.encode("utf-8")).hexdigest(),
        dimensions_digest=sha256(canonical_dimensions.encode("utf-8")).hexdigest(),
        occurred_at=timestamp,
    )


def reserve_quota_units(
    account: SubscriptionQuotaAccountState,
    *,
    reservation: UsageReservation,
) -> None:
    if account.limit_units < 0 or account.used_units < 0:
        raise SubscriptionRuntimeError("quota account counters are invalid.")
    if account.used_units > account.limit_units:
        raise SubscriptionRuntimeError("quota account is already over limit.")
    if not (account.period_start <= reservation.occurred_at < account.period_end):
        raise SubscriptionRuntimeError("usage occurred outside the quota period.")
    remaining = account.limit_units - account.used_units
    if reservation.units > remaining:
        raise SubscriptionRuntimeError("quota limit exceeded.")
    account.used_units += reservation.units
    account.version += 1
