from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from processual_api.billing.commercial_entitlement_ledger_schema_contracts import (
    BALANCES_TABLE,
    LEDGER_ENTRIES_TABLE,
    RESERVATION_LOCKS_TABLE,
)
from processual_api.db.base import Base

ENTITLEMENT_LEDGER_SQLALCHEMY_MODELS_ENABLED = False
ENTITLEMENT_LEDGER_SQLALCHEMY_RUNTIME_ENABLED = False


def _created_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CommercialEntitlementLedgerEntry(Base):
    __tablename__ = LEDGER_ENTRIES_TABLE
    __table_args__ = (
        PrimaryKeyConstraint(
            "entry_id",
            name="pk_commercial_entitlement_ledger_entries",
        ),
        CheckConstraint(
            "units > 0",
            name="units_positive",
        ),
        UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "idempotency_key",
            name=(
                "uq_commercial_entitlement_ledger_entries_"
                "scope_idempotency"
            ),
        ),
        Index(
            "ix_commercial_entitlement_ledger_entries_scope_occurred",
            "tenant_id",
            "subscription_id",
            "occurred_at",
        ),
        Index(
            "ix_commercial_entitlement_ledger_entries_reservation",
            "tenant_id",
            "subscription_id",
            "reservation_id",
            postgresql_where=text(
                "reservation_id IS NOT NULL"
            ),
        ),
        Index(
            "ix_commercial_entitlement_ledger_entries_related_entry",
            "related_entry_id",
            postgresql_where=text(
                "related_entry_id IS NOT NULL"
            ),
        ),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
    )
    related_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            (
                "commercial_entitlement_ledger_entries."
                "entry_id"
            ),
            name=(
                "fk_commercial_entitlement_ledger_entries_"
                "related_entry"
            ),
            ondelete="RESTRICT",
        ),
    )
    adjustment_units: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = _created_at_column()


class CommercialEntitlementBalance(Base):
    __tablename__ = BALANCES_TABLE
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "subscription_id",
            name="pk_commercial_entitlement_balances",
        ),
        CheckConstraint(
            "available_units >= 0",
            name="available_nonnegative",
        ),
        CheckConstraint(
            "reserved_units >= 0",
            name="reserved_nonnegative",
        ),
        CheckConstraint(
            "committed_units >= 0",
            name="committed_nonnegative",
        ),
        CheckConstraint(
            "version >= 0",
            name="version_nonnegative",
        ),
        Index(
            "ix_commercial_entitlement_balances_subscription",
            "subscription_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    available_units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )
    reserved_units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )
    committed_units: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CommercialEntitlementReservationLock(Base):
    __tablename__ = RESERVATION_LOCKS_TABLE
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "subscription_id",
            "reservation_id",
            name=(
                "pk_commercial_entitlement_reservation_locks"
            ),
        ),
        CheckConstraint(
            "length(trim(owner_token)) > 0",
            name="owner_nonblank",
        ),
        Index(
            "ix_commercial_entitlement_reservation_locks_expires",
            "expires_at",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    owner_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = _created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


@event.listens_for(
    CommercialEntitlementLedgerEntry,
    "before_update",
)
def _reject_ledger_entry_update(*_: object) -> None:
    raise ValueError(
        "commercial entitlement ledger entries are append-only"
    )


@event.listens_for(
    CommercialEntitlementLedgerEntry,
    "before_delete",
)
def _reject_ledger_entry_delete(*_: object) -> None:
    raise ValueError(
        "commercial entitlement ledger entries are append-only"
    )


COMMERCIAL_ENTITLEMENT_LEDGER_MODELS = (
    CommercialEntitlementLedgerEntry,
    CommercialEntitlementBalance,
    CommercialEntitlementReservationLock,
)


__all__ = [
    "COMMERCIAL_ENTITLEMENT_LEDGER_MODELS",
    "ENTITLEMENT_LEDGER_SQLALCHEMY_MODELS_ENABLED",
    "ENTITLEMENT_LEDGER_SQLALCHEMY_RUNTIME_ENABLED",
    *[
        model.__name__
        for model in COMMERCIAL_ENTITLEMENT_LEDGER_MODELS
    ],
]
