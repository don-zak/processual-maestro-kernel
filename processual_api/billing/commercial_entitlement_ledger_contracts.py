"""Review-only entitlement-ledger contracts for Group 2.

These contracts define immutable Maestro Unit movements and reservation
lifecycles. They do not persist entries, mutate production balances, or enable
commercial runtime enforcement.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

ENTITLEMENT_LEDGER_VERSION: Final = (
    "2026-07-group2-entitlement-ledger-v1"
)
ENTITLEMENT_LEDGER_STATUS: Final = "draft_review"

ENTITLEMENT_LEDGER_ENABLED: Final = False
ENTITLEMENT_LEDGER_PERSISTENCE_ENABLED: Final = False
MONTHLY_GRANT_LEDGER_WRITE_ENABLED: Final = False
TOP_UP_GRANT_LEDGER_WRITE_ENABLED: Final = False
USAGE_RESERVATION_LEDGER_WRITE_ENABLED: Final = False
USAGE_COMMIT_LEDGER_WRITE_ENABLED: Final = False
USAGE_RELEASE_LEDGER_WRITE_ENABLED: Final = False
USAGE_REVERSAL_LEDGER_WRITE_ENABLED: Final = False
ADMIN_ADJUSTMENT_LEDGER_WRITE_ENABLED: Final = False

IDEMPOTENCY_REQUIRED: Final = True
IMMUTABLE_LEDGER_REQUIRED: Final = True
ATOMIC_RESERVATION_REQUIRED: Final = True
NEGATIVE_BALANCE_ALLOWED_BY_DEFAULT: Final = False


class LedgerEntryType(StrEnum):
    MONTHLY_GRANT = "monthly_grant"
    TOP_UP_GRANT = "top_up_grant"
    USAGE_RESERVE = "usage_reserve"
    USAGE_COMMIT = "usage_commit"
    USAGE_RELEASE = "usage_release"
    USAGE_REVERSAL = "usage_reversal"
    REFUND_REVERSAL = "refund_reversal"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class LedgerDirection(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
    NEUTRAL = "neutral"


class ReservationState(StrEnum):
    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"
    REVERSED = "reversed"


_ENTRY_DIRECTIONS: Final[dict[LedgerEntryType, LedgerDirection]] = {
    LedgerEntryType.MONTHLY_GRANT: LedgerDirection.CREDIT,
    LedgerEntryType.TOP_UP_GRANT: LedgerDirection.CREDIT,
    LedgerEntryType.USAGE_RESERVE: LedgerDirection.NEUTRAL,
    LedgerEntryType.USAGE_COMMIT: LedgerDirection.DEBIT,
    LedgerEntryType.USAGE_RELEASE: LedgerDirection.NEUTRAL,
    LedgerEntryType.USAGE_REVERSAL: LedgerDirection.CREDIT,
    LedgerEntryType.REFUND_REVERSAL: LedgerDirection.DEBIT,
    LedgerEntryType.ADMIN_ADJUSTMENT: LedgerDirection.NEUTRAL,
}


@dataclass(frozen=True, slots=True)
class EntitlementLedgerEntry:
    entry_id: UUID
    tenant_id: UUID
    subscription_id: UUID
    entry_type: LedgerEntryType
    units: int
    idempotency_key: str
    occurred_at: datetime
    source_reference: str
    reservation_id: UUID | None = None
    related_entry_id: UUID | None = None
    adjustment_units: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError("ledger entry units must be positive")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if not self.source_reference.strip():
            raise ValueError("source_reference must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")

        if self.entry_type in {
            LedgerEntryType.USAGE_RESERVE,
            LedgerEntryType.USAGE_COMMIT,
            LedgerEntryType.USAGE_RELEASE,
            LedgerEntryType.USAGE_REVERSAL,
        } and self.reservation_id is None:
            raise ValueError(
                "usage lifecycle entries require reservation_id"
            )

        if self.entry_type is LedgerEntryType.ADMIN_ADJUSTMENT:
            if self.adjustment_units is None:
                raise ValueError(
                    "admin adjustment requires adjustment_units"
                )
            if self.adjustment_units == 0:
                raise ValueError(
                    "admin adjustment must not be zero"
                )
            if not self.reason or not self.reason.strip():
                raise ValueError(
                    "admin adjustment requires an audit reason"
                )
        elif self.adjustment_units is not None:
            raise ValueError(
                "adjustment_units are valid only for admin adjustment"
            )

        if self.entry_type in {
            LedgerEntryType.USAGE_REVERSAL,
            LedgerEntryType.REFUND_REVERSAL,
        } and self.related_entry_id is None:
            raise ValueError(
                "reversal entries require related_entry_id"
            )

    @property
    def direction(self) -> LedgerDirection:
        if self.entry_type is LedgerEntryType.ADMIN_ADJUSTMENT:
            assert self.adjustment_units is not None
            return (
                LedgerDirection.CREDIT
                if self.adjustment_units > 0
                else LedgerDirection.DEBIT
            )
        return _ENTRY_DIRECTIONS[self.entry_type]

    @property
    def signed_units(self) -> int:
        if self.entry_type is LedgerEntryType.ADMIN_ADJUSTMENT:
            assert self.adjustment_units is not None
            return self.adjustment_units

        if self.direction is LedgerDirection.CREDIT:
            return self.units
        if self.direction is LedgerDirection.DEBIT:
            return -self.units
        return 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["entry_id"] = str(self.entry_id)
        payload["tenant_id"] = str(self.tenant_id)
        payload["subscription_id"] = str(self.subscription_id)
        payload["entry_type"] = self.entry_type.value
        payload["direction"] = self.direction.value
        payload["signed_units"] = self.signed_units
        payload["occurred_at"] = self.occurred_at.astimezone(
            UTC
        ).isoformat()
        payload["reservation_id"] = (
            None
            if self.reservation_id is None
            else str(self.reservation_id)
        )
        payload["related_entry_id"] = (
            None
            if self.related_entry_id is None
            else str(self.related_entry_id)
        )
        return payload


@dataclass(frozen=True, slots=True)
class EntitlementBalanceSnapshot:
    tenant_id: UUID
    subscription_id: UUID
    available_units: int
    reserved_units: int
    committed_units: int
    calculated_at: datetime

    def __post_init__(self) -> None:
        values = (
            self.available_units,
            self.reserved_units,
            self.committed_units,
        )
        if any(value < 0 for value in values):
            raise ValueError(
                "balance snapshot values must not be negative"
            )
        if self.calculated_at.tzinfo is None:
            raise ValueError(
                "calculated_at must be timezone-aware"
            )

    def can_reserve(
        self,
        requested_units: int,
        *,
        contracted_overage_units: int = 0,
    ) -> bool:
        if requested_units <= 0:
            raise ValueError(
                "requested_units must be positive"
            )
        if contracted_overage_units < 0:
            raise ValueError(
                "contracted_overage_units must not be negative"
            )

        spendable = (
            self.available_units + contracted_overage_units
        )
        return requested_units <= spendable


@dataclass(frozen=True, slots=True)
class UsageReservationDecision:
    approved: bool
    reservation_id: UUID
    requested_units: int
    available_units: int
    contracted_overage_units: int
    reason: str
    ledger_write_enabled: bool = (
        USAGE_RESERVATION_LEDGER_WRITE_ENABLED
    )

    def __post_init__(self) -> None:
        if self.requested_units <= 0:
            raise ValueError(
                "requested_units must be positive"
            )
        if self.available_units < 0:
            raise ValueError(
                "available_units must not be negative"
            )
        if self.contracted_overage_units < 0:
            raise ValueError(
                "contracted_overage_units must not be negative"
            )
        if self.ledger_write_enabled:
            raise ValueError(
                "ledger writes must remain disabled in draft review"
            )


def decide_usage_reservation(
    *,
    snapshot: EntitlementBalanceSnapshot,
    reservation_id: UUID,
    requested_units: int,
    contracted_overage_units: int = 0,
) -> UsageReservationDecision:
    """Return a review-only reservation decision."""

    approved = snapshot.can_reserve(
        requested_units,
        contracted_overage_units=contracted_overage_units,
    )

    return UsageReservationDecision(
        approved=approved,
        reservation_id=reservation_id,
        requested_units=requested_units,
        available_units=snapshot.available_units,
        contracted_overage_units=contracted_overage_units,
        reason=(
            "sufficient owned balance or contracted overage"
            if approved
            else "insufficient owned balance and contracted overage"
        ),
    )


def calculate_balance_from_entries(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> int:
    """Calculate signed balance without persisting or mutating entries."""

    seen_idempotency_keys: set[str] = set()
    balance = 0

    for entry in entries:
        if entry.idempotency_key in seen_idempotency_keys:
            raise ValueError(
                "duplicate ledger idempotency key"
            )
        seen_idempotency_keys.add(entry.idempotency_key)
        balance += entry.signed_units

    if (
        balance < 0
        and not NEGATIVE_BALANCE_ALLOWED_BY_DEFAULT
    ):
        raise ValueError(
            "ledger entries produce a negative balance"
        )

    return balance


def entitlement_ledger_review_payload() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_LEDGER_VERSION,
        "status": ENTITLEMENT_LEDGER_STATUS,
        "enabled": ENTITLEMENT_LEDGER_ENABLED,
        "persistence_enabled": (
            ENTITLEMENT_LEDGER_PERSISTENCE_ENABLED
        ),
        "monthly_grant_write_enabled": (
            MONTHLY_GRANT_LEDGER_WRITE_ENABLED
        ),
        "top_up_grant_write_enabled": (
            TOP_UP_GRANT_LEDGER_WRITE_ENABLED
        ),
        "usage_reservation_write_enabled": (
            USAGE_RESERVATION_LEDGER_WRITE_ENABLED
        ),
        "usage_commit_write_enabled": (
            USAGE_COMMIT_LEDGER_WRITE_ENABLED
        ),
        "usage_release_write_enabled": (
            USAGE_RELEASE_LEDGER_WRITE_ENABLED
        ),
        "usage_reversal_write_enabled": (
            USAGE_REVERSAL_LEDGER_WRITE_ENABLED
        ),
        "admin_adjustment_write_enabled": (
            ADMIN_ADJUSTMENT_LEDGER_WRITE_ENABLED
        ),
        "idempotency_required": IDEMPOTENCY_REQUIRED,
        "immutable_ledger_required": IMMUTABLE_LEDGER_REQUIRED,
        "atomic_reservation_required": (
            ATOMIC_RESERVATION_REQUIRED
        ),
        "negative_balance_allowed_by_default": (
            NEGATIVE_BALANCE_ALLOWED_BY_DEFAULT
        ),
    }


__all__ = [
    "ADMIN_ADJUSTMENT_LEDGER_WRITE_ENABLED",
    "ATOMIC_RESERVATION_REQUIRED",
    "ENTITLEMENT_LEDGER_ENABLED",
    "ENTITLEMENT_LEDGER_PERSISTENCE_ENABLED",
    "ENTITLEMENT_LEDGER_STATUS",
    "ENTITLEMENT_LEDGER_VERSION",
    "EntitlementBalanceSnapshot",
    "EntitlementLedgerEntry",
    "IDEMPOTENCY_REQUIRED",
    "IMMUTABLE_LEDGER_REQUIRED",
    "LedgerDirection",
    "LedgerEntryType",
    "MONTHLY_GRANT_LEDGER_WRITE_ENABLED",
    "NEGATIVE_BALANCE_ALLOWED_BY_DEFAULT",
    "ReservationState",
    "TOP_UP_GRANT_LEDGER_WRITE_ENABLED",
    "USAGE_COMMIT_LEDGER_WRITE_ENABLED",
    "USAGE_RELEASE_LEDGER_WRITE_ENABLED",
    "USAGE_RESERVATION_LEDGER_WRITE_ENABLED",
    "USAGE_REVERSAL_LEDGER_WRITE_ENABLED",
    "UsageReservationDecision",
    "calculate_balance_from_entries",
    "decide_usage_reservation",
    "entitlement_ledger_review_payload",
]
